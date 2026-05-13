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
    Includes every CCBI with the expected ibcc header; any scene-specific parse
    problem is reported when that scene is selected instead of hiding the file."""

    candidates = []
    for ccbi in sorted(assets.rglob("*.ccbi"), key=lambda p: (
        0 if "loading_screens_ccbi_240" in str(p.relative_to(assets)).lower().replace("\\", "/") else 1,
        str(p.relative_to(assets)).lower(),
    )):
        try:
            with open(ccbi, "rb") as f:
                if f.read(4) != b"ibcc":
                    continue
        except OSError:
            continue
        candidates.append(ccbi)

    result = []
    for ccbi in candidates:
        rel = ccbi.relative_to(assets)
        display = re.sub(r"-v\d+$", "", str(rel.with_suffix("")))
        display = display.replace("\\", " / ").replace("_", " ").strip().title()
        result.append((display, ccbi))
    return result


_PORTRAIT_REF_RE = re.compile(rb"(portrait_[a-z0-9_]+?)-v\d+\.(?:png|plist)")
_CCBI_REF_RE = re.compile(rb"/assets/([a-z0-9_./\\-]+?)-v\d+\.ccbi")


def discover_character_books(books_root: Path, on_progress=None) -> dict:
    """
    For each book directory under *books_root*, scan every chapter .protobin
    for portrait file references and return {book_dir_name: set(portrait_stem)}.

    Each chapter's protobin field-3 asset manifest contains URLs like
    `…/assets/portraits/{res}/portrait_anime_main_jake-v01.png` for every
    portrait, NPC, animal, and custom-builder layer used in that chapter.
    Extracting the version-less stems gives a complete and exact set of
    portraits-per-book — no heuristics, no false positives.

    Cached by file path + mtime; only changed/new chapters are re-parsed.
    """
    if not books_root.exists():
        return {}

    candidates = []  # (book_name, protobin_path)
    for bdir in sorted(books_root.iterdir()):
        if not bdir.is_dir():
            continue
        for pbin in sorted(bdir.glob("*.protobin")):
            candidates.append((bdir.name, pbin))

    cache_file = _cache_path(books_root, "char_books")
    cache = _load_cache(cache_file)

    def _stems_for(pbin):
        try:
            data = pbin.read_bytes()
        except OSError:
            return []
        return sorted({m.group(1).decode("ascii") for m in _PORTRAIT_REF_RE.finditer(data)})

    to_parse = []
    to_parse_idx = []
    stem_lists: list = [None] * len(candidates)
    for i, (_book, pbin) in enumerate(candidates):
        try:
            mtime = pbin.stat().st_mtime
        except OSError:
            continue
        key = str(pbin)
        cached = cache.get(key)
        if cached and cached.get("mtime") == mtime:
            stem_lists[i] = cached.get("stems", [])
        else:
            to_parse.append(pbin)
            to_parse_idx.append((i, key, mtime))

    fresh = _parallel_map(_stems_for, to_parse, on_progress, "Indexing book characters")
    new_cache = dict(cache)
    for (i, key, mtime), stems in zip(to_parse_idx, fresh):
        stem_lists[i] = stems
        new_cache[key] = {"mtime": mtime, "stems": stems}

    live_keys = {str(c[1]) for c in candidates}
    new_cache = {k: v for k, v in new_cache.items() if k in live_keys}
    if new_cache != cache:
        _save_cache(cache_file, new_cache)

    book_stems: dict = {}
    for (book, _pbin), stems in zip(candidates, stem_lists):
        if not stems:
            continue
        book_stems.setdefault(book, set()).update(stems)
    return book_stems


def discover_scene_books(books_root: Path, on_progress=None) -> dict:
    """
    For each book directory under *books_root*, scan chapter .protobin files for
    CCBI references and return {book_dir_name: set(scene_keys)}.
    """
    if not books_root.exists():
        return {}

    candidates = []
    for bdir in sorted(books_root.iterdir()):
        if not bdir.is_dir():
            continue
        for pbin in sorted(bdir.glob("*.protobin")):
            candidates.append((bdir.name, pbin))

    cache_file = _cache_path(books_root, "scene_books")
    cache = _load_cache(cache_file)

    def _keys_for(pbin):
        try:
            data = pbin.read_bytes()
        except OSError:
            return []
        keys = set()
        for m in _CCBI_REF_RE.finditer(data):
            rel = m.group(1).decode("ascii", "ignore").replace("\\", "/")
            keys.add(rel)
            keys.add(Path(rel).name)
        return sorted(keys)

    to_parse = []
    to_parse_idx = []
    key_lists: list = [None] * len(candidates)
    for i, (_book, pbin) in enumerate(candidates):
        try:
            mtime = pbin.stat().st_mtime
        except OSError:
            continue
        key = str(pbin)
        cached = cache.get(key)
        if cached and cached.get("mtime") == mtime:
            key_lists[i] = cached.get("keys", [])
        else:
            to_parse.append(pbin)
            to_parse_idx.append((i, key, mtime))

    fresh = _parallel_map(_keys_for, to_parse, on_progress, "Indexing book scenes")
    new_cache = dict(cache)
    for (i, key, mtime), keys in zip(to_parse_idx, fresh):
        key_lists[i] = keys
        new_cache[key] = {"mtime": mtime, "keys": keys}

    live_keys = {str(c[1]) for c in candidates}
    new_cache = {k: v for k, v in new_cache.items() if k in live_keys}
    if new_cache != cache:
        _save_cache(cache_file, new_cache)

    book_scenes: dict = {}
    for (book, _pbin), keys in zip(candidates, key_lists):
        if not keys:
            continue
        book_scenes.setdefault(book, set()).update(keys)
    return book_scenes


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
