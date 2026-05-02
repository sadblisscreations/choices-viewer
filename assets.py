import hashlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


_CACHE_DIR = Path.home() / ".choices_viewer_cache"


def _cache_path(assets: Path, kind: str) -> Path:
    h = hashlib.md5(str(assets.resolve()).encode("utf-8")).hexdigest()[:12]
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{h}_{kind}.json"


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_cache(path: Path, data: dict):
    try:
        path.write_text(json.dumps(data))
    except Exception:
        pass


def _parallel_map(fn, items, on_progress=None, stage=""):
    if not items:
        return []
    workers = min(32, (os.cpu_count() or 4) * 4)
    results = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fn, item): i for i, item in enumerate(items)}
        done = 0
        total = len(items)
        for fut in futures:
            pass
        from concurrent.futures import as_completed
        for fut in as_completed(futures):
            i = futures[fut]
            results[i] = fut.result()
            done += 1
            if on_progress:
                on_progress(stage, done, total)
    return results


def validate_dlc_path(path: Path) -> "Path | None":
    for candidate in [path, path / "assets"]:
        if (candidate / "portraits").exists() or \
           (candidate / "portraits_large").exists():
            return candidate
    return None


def portrait_dirs(assets: Path) -> list:
    return [
        assets / "portraits_large" / "non_custom" / "2x",
        assets / "portraits" / "2x",
    ]


def find_characters(assets: Path) -> list:
    chars, seen = [], set()
    for d in portrait_dirs(assets):
        if not d.exists():
            continue
        for plist in sorted(d.glob("*.plist")):
            png = plist.with_suffix(".png")
            if not png.exists() or plist.stem in seen:
                continue
            seen.add(plist.stem)
            name = (
                plist.stem.split("-v")[0]
                .removeprefix("portrait_")
                .replace("_", " ")
                .title()
            )
            chars.append((name, png, plist))
    return chars


def discover_custom_items(assets: Path) -> dict:
    """
    Returns {char_type: {slot: [(label, plist_path, png_path)]}}
    Deduplicates by keeping the highest version of each item.
    """
    custom_dir = assets / "portraits_large" / "custom" / "2x"
    if not custom_dir.exists():
        return {}

    # seen[char_type][slot][base_name] = (version, label, plist, png)
    seen: dict = {}

    for plist in sorted(custom_dir.glob("item_*.plist")):
        png = plist.with_suffix(".png")
        if not png.exists():
            continue

        stem = plist.stem
        m = re.match(r"^(.*)-v(\d+)$", stem)
        base_name = m.group(1) if m else stem
        version   = int(m.group(2)) if m else 0

        parts = base_name.split("_")
        if len(parts) < 4:
            continue

        gender, role = parts[1], parts[2]
        char_type    = f"{gender}_{role}"
        cat          = parts[3]

        if cat in ("hair", "hat", "prop", "acc") and len(parts) > 4 and parts[4] in ("b", "f"):
            slot        = f"{cat}_{parts[4]}"
            label_parts = parts[5:]
        else:
            slot        = cat
            label_parts = parts[4:]

        label = " ".join(label_parts).title() or base_name

        ct_dict   = seen.setdefault(char_type, {})
        slot_dict = ct_dict.setdefault(slot, {})
        existing  = slot_dict.get(base_name)
        if existing is None or version > existing[0]:
            slot_dict[base_name] = (version, label, plist, png)

    result = {}
    for ct, slots in seen.items():
        result[ct] = {}
        for slot, items_dict in slots.items():
            entries = sorted(items_dict.values(), key=lambda x: x[1])
            result[ct][slot] = [(lbl, p, n) for _, lbl, p, n in entries]
    return result


def discover_portrait_layers(assets: Path, on_progress=None) -> dict:
    """
    Returns non-custom portrait characters in the same format as
    discover_custom_items(): {char_type: {slot: [(label, plist_path, png_path)]}}

    Groups portraits by role (portrait_male, portrait_female, etc.) and maps
    each portrait's sprite keys to custom builder slots so they can be mixed
    in the Custom tab.
    """
    from .parsers.plist_parser import parse_plist

    _KEY_SLOT = {
        "BODY.png":   "body",
        "HAIR_B.png": "hair_b",
        "HAIR_F.png": "hair_f",
        "PROP_F.png": "prop_f",
        "PROP_B.png": "prop_b",
        "ACC_F.png":  "acc",
        "ACC_B.png":  "acc",
    }

    portrait_dir = assets / "portraits_large" / "non_custom" / "2x"
    if not portrait_dir.exists():
        return {}

    # Pre-filter and gather metadata before doing the expensive plist parse.
    candidates = []
    for plist in sorted(portrait_dir.glob("*.plist")):
        png = plist.with_suffix(".png")
        if not png.exists():
            continue

        stem = plist.stem
        m = re.match(r"^(.*)-v(\d+)$", stem)
        base_name = m.group(1) if m else stem
        version   = int(m.group(2)) if m else 0

        parts = base_name.split("_")
        if len(parts) < 3 or parts[0] != "portrait":
            continue

        book      = parts[1]
        role      = parts[2]
        char_type = f"portrait_{role}"

        name_parts = parts[3:]
        if name_parts:
            label = f"{book.title()} - {' '.join(name_parts).title()}"
        else:
            label = f"{book.title()} {role.title()}"

        candidates.append((plist, png, base_name, version, char_type, label))

    # Cache parsed slot-sets keyed by path + mtime.  Re-parse only files that
    # are new or whose mtime changed; everything else reuses the cached value.
    cache_file = _cache_path(assets, "portrait_slots")
    cache = _load_cache(cache_file)

    def _slots_for(plist_path):
        try:
            sprites = parse_plist(plist_path)
        except Exception:
            return None
        present: set = set()
        for key in sprites:
            if key in _KEY_SLOT:
                present.add(_KEY_SLOT[key])
            elif key.startswith("FACE_"):
                present.add("face")
        return sorted(present)

    to_parse = []
    to_parse_idx = []
    slot_sets: list = [None] * len(candidates)
    for i, (plist, *_rest) in enumerate(candidates):
        try:
            mtime = plist.stat().st_mtime
        except OSError:
            continue
        key = str(plist)
        cached = cache.get(key)
        if cached and cached.get("mtime") == mtime:
            slot_sets[i] = cached.get("slots")
        else:
            to_parse.append(plist)
            to_parse_idx.append((i, key, mtime))

    fresh = _parallel_map(_slots_for, to_parse, on_progress, "Parsing portrait atlases")
    new_cache = dict(cache)
    for (i, key, mtime), slots in zip(to_parse_idx, fresh):
        slot_sets[i] = slots
        new_cache[key] = {"mtime": mtime, "slots": slots}

    # Drop cache entries for files that no longer exist
    live_keys = {str(c[0]) for c in candidates}
    new_cache = {k: v for k, v in new_cache.items() if k in live_keys}
    if new_cache != cache:
        _save_cache(cache_file, new_cache)

    # {char_type: {slot: {base_name: (version, label, plist, png)}}}
    seen: dict = {}
    for (plist, png, base_name, version, char_type, label), present_slots in zip(candidates, slot_sets):
        if not present_slots:
            continue
        ct_dict = seen.setdefault(char_type, {})
        for slot in present_slots:
            slot_dict = ct_dict.setdefault(slot, {})
            existing  = slot_dict.get(base_name)
            if existing is None or version > existing[0]:
                slot_dict[base_name] = (version, label, plist, png)

    result: dict = {}
    for ct, slots in seen.items():
        result[ct] = {}
        for slot, items_dict in slots.items():
            entries = sorted(items_dict.values(), key=lambda x: x[1])
            result[ct][slot] = [(lbl, p, n) for _, lbl, p, n in entries]
    return result


def discover_ccbi_scenes(assets: Path, on_progress=None) -> list:
    """Return [(display_name, ccbi_path)] sorted by display_name.
    Only includes files that pass a full parse.  Parse results are cached by
    file path + mtime, so subsequent launches skip files known to parse OK."""
    from .parsers.ccbi_parser import parse_ccbi_file

    ccbi_dir = assets / "ccbi"
    if not ccbi_dir.exists():
        return []

    candidates = []
    for ccbi in sorted(ccbi_dir.glob("*.ccbi")):
        try:
            with open(ccbi, "rb") as f:
                if f.read(4) != b"ibcc":
                    continue
        except OSError:
            continue
        candidates.append(ccbi)

    cache_file = _cache_path(assets, "ccbi_ok")
    cache = _load_cache(cache_file)

    def _ok(path):
        try:
            parse_ccbi_file(path)
            return True
        except Exception:
            return False

    to_parse = []
    to_parse_idx = []
    ok_flags: list = [None] * len(candidates)
    for i, ccbi in enumerate(candidates):
        try:
            mtime = ccbi.stat().st_mtime
        except OSError:
            continue
        key = str(ccbi)
        cached = cache.get(key)
        if cached and cached.get("mtime") == mtime:
            ok_flags[i] = cached.get("ok", False)
        else:
            to_parse.append(ccbi)
            to_parse_idx.append((i, key, mtime))

    fresh = _parallel_map(_ok, to_parse, on_progress, "Validating scenes")
    new_cache = dict(cache)
    for (i, key, mtime), ok in zip(to_parse_idx, fresh):
        ok_flags[i] = ok
        new_cache[key] = {"mtime": mtime, "ok": ok}

    live_keys = {str(c) for c in candidates}
    new_cache = {k: v for k, v in new_cache.items() if k in live_keys}
    if new_cache != cache:
        _save_cache(cache_file, new_cache)

    result = []
    for ccbi, ok in zip(candidates, ok_flags):
        if not ok:
            continue
        display = re.sub(r"-v\d+$", "", ccbi.stem)
        display = display.replace("_", " ").strip().title()
        result.append((display, ccbi))
    return result


def discover_books(books_root: Path) -> list:
    """
    Return [(book_name, [(chapter_display, chapter_path)])] sorted.
    books_root is typically .../dlc_cache/books.
    """
    if not books_root.exists():
        return []
    result = []
    for book_dir in sorted(books_root.iterdir()):
        if not book_dir.is_dir():
            continue
        chapters = []
        for protobin in sorted(book_dir.glob("*.protobin")):
            display = re.sub(r"-v\d+$", "", protobin.stem)
            display = display.replace("_", " ").strip().title()
            chapters.append((display, protobin))
        if chapters:
            name = book_dir.name.replace("_", " ").strip().title()
            result.append((name, chapters))
    return result


def discover_spritesheets(assets: Path) -> list:
    """Return [(display_name, plist_path, png_path)] sorted by display_name."""
    sheet_dir = assets / "ccbi_spritesheets" / "large"
    if not sheet_dir.exists():
        return []
    result = []
    for plist in sorted(sheet_dir.glob("*.plist")):
        png = plist.with_suffix(".png")
        if not png.exists():
            continue
        stem = plist.stem
        display = re.sub(r"-v\d+$", "", stem)
        display = re.sub(r"^bgz?_", "", display)
        display = display.replace("_", " ").strip().title()
        result.append((display, plist, png))
    return result
