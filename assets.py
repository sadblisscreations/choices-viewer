import re
from pathlib import Path


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

        if cat in ("hair", "hat", "prop") and len(parts) > 4 and parts[4] in ("b", "f"):
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
