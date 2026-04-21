import re
from pathlib import Path

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QTransform

from .parsers.plist_parser import parse_plist

# ── Character layer constants ─────────────────────────────────────────────────

LAYER_ORDER = ["HAIR_B.png", "BODY.png", "FACE_{e}.png", "HAIR_F.png", "PROP_F.png"]
EMOTIONS    = ["NEUTRAL", "HAPPY", "ANGRY", "SAD", "SURPRISED"]

# ── Portrait → custom slot key mapping ───────────────────────────────────────

_PORTRAIT_SLOT_KEY = {
    "body":   "BODY.png",
    "hair_b": "HAIR_B.png",
    "hair_f": "HAIR_F.png",
    "prop_f": "PROP_F.png",
    "prop_b": "PROP_B.png",
    "acc":    "ACC_F.png",
}


def resolve_sprite_key(sprites: dict, slot: str, emotion: str) -> "str | None":
    """
    Return the best sprite key for a given slot + emotion.
    Tries custom-item keys first (NEUTRAL.png / emotion.png for face), then
    falls back to portrait-style keys (BODY.png / FACE_*.png etc.).
    """
    if slot == "face":
        for key in (
            f"{emotion}.png",
            "NEUTRAL.png",
            f"FACE_{emotion}.png",
            "FACE_NEUTRAL.png",
        ):
            if key in sprites:
                return key
    else:
        portrait_key = _PORTRAIT_SLOT_KEY.get(slot)
        for key in ("NEUTRAL.png", portrait_key):
            if key and key in sprites:
                return key
    return None


# ── Custom character layer constants ──────────────────────────────────────────

# Bottom-to-top render order
CUSTOM_LAYER_ORDER = ["prop_b", "hat_b", "hair_b", "body", "clothing", "tattoo", "scarf", "face", "hair_f", "hat_f", "prop_f", "acc_b", "acc"]
CUSTOM_OPTIONAL    = frozenset(["prop_b", "hat_b", "hat_f", "prop_f", "scarf", "acc_b", "acc", "tattoo"])

SLOT_LABELS = {
    "prop_b":   "Prop Back",
    "hat_b":    "Hat Back",
    "body":     "Body / Skin",
    "face":     "Face",
    "hair_b":   "Hair Back",
    "hair_f":   "Hair Front",
    "clothing": "Clothing",
    "hat_f":    "Hat",
    "prop_f":   "Prop",
    "scarf":    "Scarf / Strap",
    "acc_b":    "Accessory Back",
    "acc":      "Accessory",
    "tattoo":   "Tattoo",
}


# ── Atlas loading (with PIL fallback for non-standard PNG formats) ─────────────

def _load_atlas(path: Path) -> QImage:
    img = QImage(str(path))
    if not img.isNull():
        return img
    try:
        from PIL import Image as PILImage
        import numpy as np
        pil = PILImage.open(str(path)).convert("RGBA")
        arr = np.asarray(pil, dtype=np.uint8).copy()
        # PIL RGBA → Qt Format_ARGB32 in memory (BGRA): swap R↔B
        arr[:, :, [0, 2]] = arr[:, :, [2, 0]]
        h, w = arr.shape[:2]
        return QImage(arr.data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()
    except Exception:
        return QImage()


# ── Character compositing ─────────────────────────────────────────────────────

def composite(atlas_path: Path, sprites: dict, emotion: str) -> "QPixmap | None":
    layers = [t.replace("{e}", emotion) for t in LAYER_ORDER if t.replace("{e}", emotion) in sprites]
    if not layers:
        return None
    atlas = _load_atlas(atlas_path)
    if atlas.isNull():
        return None
    max_w = max_h = 0
    for lyr in layers:
        _, _, _, _, _, _, ow, oh, _ = sprites[lyr]
        max_w = max(max_w, round(ow)); max_h = max(max_h, round(oh))
    if max_w < 1 or max_h < 1:
        return None
    canvas = QImage(max_w, max_h, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    for lyr in layers:
        sx, sy, sw, sh, ox, oy, ow, oh, rotated = sprites[lyr]
        px = round((ow - sw) / 2 + ox)
        py = round((oh - sh) / 2 - oy)
        if rotated:
            tile = atlas.copy(QRect(round(sx), round(sy), round(sh), round(sw)))
            tile = tile.transformed(QTransform().rotate(-90))
            p.drawImage(QRect(px, py, round(sw), round(sh)), tile)
        else:
            p.drawImage(QRect(px, py, round(sw), round(sh)),
                        atlas, QRect(round(sx), round(sy), round(sw), round(sh)))
    p.end()
    return QPixmap.fromImage(canvas)


# ── Custom character compositing ──────────────────────────────────────────────

def composite_custom(selections: dict, emotion: str) -> "QPixmap | None":
    """
    Composite individual item sprites onto a shared canvas.
    selections: {slot: (plist_path, png_path)}

    Each item may have a different orig_size (e.g. wide ballgowns vs normal outfits).
    We determine the maximum canvas first, then position every sprite relative to
    that shared canvas — equivalent to adding (canvas - orig) / 2 as a centering
    offset so that sprites designed for narrower canvases stay centred correctly.
    """
    canvas_w = canvas_h = 0
    layers_data = []

    for slot in CUSTOM_LAYER_ORDER:
        item = selections.get(slot)
        if item is None:
            continue
        plist_path, png_path = item
        sprites = parse_plist(plist_path)

        key = resolve_sprite_key(sprites, slot, emotion)
        if key is None:
            continue

        sx, sy, sw, sh, ox, oy, ow, oh, rotated = sprites[key]
        canvas_w = max(canvas_w, round(ow))
        canvas_h = max(canvas_h, round(oh))
        layers_data.append((str(png_path), sx, sy, sw, sh, ox, oy, rotated))

    if not layers_data or canvas_w < 1 or canvas_h < 1:
        return None

    canvas = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    for png_path, sx, sy, sw, sh, ox, oy, rotated in layers_data:
        atlas = _load_atlas(Path(png_path))
        if atlas.isNull():
            continue
        px = round((canvas_w - sw) / 2 + ox)
        py = round((canvas_h - sh) / 2 - oy)
        if rotated:
            tile = atlas.copy(QRect(round(sx), round(sy), round(sh), round(sw)))
            tile = tile.transformed(QTransform().rotate(-90))
            p.drawImage(QRect(px, py, round(sw), round(sh)), tile)
        else:
            p.drawImage(QRect(px, py, round(sw), round(sh)),
                        atlas, QRect(round(sx), round(sy), round(sw), round(sh)))

    p.end()
    return QPixmap.fromImage(canvas)


# ── Spritesheet compositing ───────────────────────────────────────────────────

def _ccbi_static_frame_names(ccbi_path: Path, plist_names: set) -> "set | None":
    """
    Parse a CCBI (ibcc) file and return the set of plist sprite names that appear
    as initial CCSprite displayFrame property values (i.e., before the first
    animation-sequence name in the file).

    In the ibcc string table, strings are written in the order they are first
    referenced.  Node-tree property values (static displayFrames) appear before
    sequence/timeline names; keyframe targets appear after.  So any plist sprite
    name whose first occurrence in the file is before the first TIMELINE_* /
    "Default Timeline" string is a simultaneous static node, not an animation key.

    Returns None if the file cannot be read.
    """
    try:
        data = ccbi_path.read_bytes()
    except OSError:
        return None

    # Extract all 4+ char printable-ASCII runs with byte offsets.
    matches = [(m.start(), m.group().decode("ascii", errors="replace"))
               for m in re.finditer(rb"[\x20-\x7e]{4,}", data)]

    # In the ibcc string table each string is length-prefixed with a varint.
    # For lengths ≤ 127 the varint is one byte.  If that byte falls in the
    # printable-ASCII range (0x20–0x7e) the regex run includes it, so the
    # actual string value is s[1:].  We detect this by checking whether
    # len(s) − 1 == ord(s[0]), i.e. the leading byte really is a matching
    # length prefix.  When the length byte is < 0x20 (non-printable) the
    # regex starts at the first real character and s is already the bare value.

    def _bare(s: str) -> str:
        """Return the string value, stripping the length-prefix byte if present."""
        if len(s) > 1 and len(s) - 1 == ord(s[0]):
            return s[1:]
        return s

    def _is_timeline(s: str) -> bool:
        b = _bare(s)
        return b.startswith("TIMELINE_") or b == "Default Timeline"

    # First occurrence of any timeline/sequence name marks the boundary.
    timeline_offset = next(
        (off for off, s in matches if _is_timeline(s)),
        len(data),
    )

    # Collect sprite names whose first occurrence is before the timeline section.
    static_names: set = set()
    for off, s in matches:
        if off >= timeline_offset:
            break
        candidate = _bare(s)
        if candidate in plist_names:
            static_names.add(candidate)

    return static_names


def analyze_spritesheet(sprites: dict, ccbi_path: "Path | None" = None) -> tuple:
    """
    Group sprites into animation layers by stripping trailing _NN frame numbers.
    Returns (canvas_w, canvas_h, frame_count, layer_order, layer_frames, frame_offset)
      layer_frames: {base_name: {frame_num_or_None: sprite_key}}
                    None key = no numeric suffix (static layer, drawn every frame)
      frame_count : number of frames (>=1)
      frame_offset: value to add to frame_idx to get frame_num (usually 1, 0 if sheet starts at _00)

    ccbi_path: optional path to the matching .ccbi scene file.  When provided,
               it is used to determine which multi-frame bases are simultaneous
               static depth-layers (vs temporal animations), overriding the
               position-spread heuristic for those bases.
    """
    from collections import Counter

    canvas_w = canvas_h = 0
    for sx, sy, sw, sh, ox, oy, ow, oh, rot in sprites.values():
        canvas_w = max(canvas_w, round(ow))
        canvas_h = max(canvas_h, round(oh))

    # Build layer_frames; use None (not 0) for sprites with no numeric suffix.
    layer_frames_raw: dict = {}
    for name in sprites:
        m = re.match(r"^(.+?)_(\d+)\.png$", name)
        if m:
            base, num = m.group(1), int(m.group(2))
        else:
            base = name
            num  = None
        layer_frames_raw.setdefault(base, {})[num] = name

    # Detect variant/costume sheets:
    # A base whose numbered frames are spread across very different canvas positions
    # is a "depth-layer" base — its _NN sprites tile spatially (shown all at once)
    # rather than temporally (shown one at a time).
    # When ≥2 depth-layer bases share the same frame-number set, the sheet is a
    # costume/scene-element composite, not a temporal animation.
    # Example: gown_angel{1,2,3} at y≈400/700/730 and gown_devil{1,2,3} at y≈400/700/730
    # are both depth-layer bases sharing {1,2,3} → variant composite.
    # Contrast: l_fang{1,2} and r_fang{1,2} at similar canvas positions
    # → NOT depth-layer → normal 2-frame animation.
    _DEPTH_SPREAD_PX = 200  # frames further apart than this are spatial layers, not time steps

    def _pos_spread(base: str, fmap: dict) -> float:
        nums = [k for k in fmap if k is not None]
        if len(nums) < 2:
            return 0.0
        pts = []
        for n in nums:
            sx, sy, sw, sh, ox, oy, ow, oh, rot = sprites[fmap[n]]
            pts.append(((ow - sw) / 2 + ox, (oh - sh) / 2 - oy))
        dx = max(p[0] for p in pts) - min(p[0] for p in pts)
        dy = max(p[1] for p in pts) - min(p[1] for p in pts)
        return max(dx, dy)

    # Optional CCBI-based depth-layer override.
    # Sprite names that appear before the first timeline sequence name in the
    # CCBI are initial CCSprite displayFrame values (simultaneous static nodes).
    # When ALL frames of a multi-frame base are in this set, the base is a
    # spatial depth-layer regardless of position spread.
    ccbi_static: "set | None" = None
    if ccbi_path is not None:
        ccbi_static = _ccbi_static_frame_names(ccbi_path, set(sprites.keys()))

    def _is_depth_layer(base: str, fmap: dict) -> bool:
        nums = [k for k in fmap if k is not None]
        if len(nums) < 2:
            return False
        # CCBI override — limited to exactly 2-frame bases:
        # If both frames appear as initial CCSprite displayFrame values (before the
        # first timeline sequence name), they are two separate simultaneous nodes,
        # not two keyframes of the same animated sprite.
        # We restrict this to n==2 to avoid false positives from visibility-based
        # animations (where each animation frame is a separate CCSprite node whose
        # visibility is toggled by the timeline — all frames appear as initial
        # displayFrames even though only one is visible at a time).  Those cases
        # typically have n≥4 frames; n==2 spatial depth pairs are common and safe.
        if ccbi_static is not None and len(nums) == 2:
            if all(fmap[n] in ccbi_static for n in nums):
                return True
        # Fallback: large position spread → spatial depth layers.
        return _pos_spread(base, fmap) > _DEPTH_SPREAD_PX

    depth_layer_bases = {
        base: frozenset(k for k in fmap if k is not None)
        for base, fmap in layer_frames_raw.items()
        if _is_depth_layer(base, fmap)
    }
    set_counts = Counter(depth_layer_bases.values()) if depth_layer_bases else {}
    is_variant  = any(count >= 2 for count in set_counts.values())

    if is_variant:
        # Every sprite is an independent static layer; show all at once.
        layer_frames = {name: {None: name} for name in sprites}
        return canvas_w, canvas_h, 1, list(layer_frames.keys()), layer_frames, 1

    # Expand depth-layer bases into individual static layers (preserve render order).
    # A depth-layer base has frames at very different canvas positions — they are
    # shown simultaneously as z-ordered planes, not alternated as animation frames.
    # Example: parlor_magical dish_01…dish_13 at 13 different positions on the scene,
    # mirror_ripples mask_01…mask_05 overlaid at different spots.
    layer_frames = {}
    for base, fmap in layer_frames_raw.items():
        if base in depth_layer_bases:
            for num in sorted(k for k in fmap if k is not None):
                layer_frames[f"{base}_{num}"] = {None: fmap[num]}
        else:
            layer_frames[base] = fmap

    # Compute frame range only from bases with ≥2 frames (true animated bases).
    # Single-frame bases are static regardless of their frame number — excluding
    # them prevents oddly-numbered lone sprites (e.g. _band_50) from inflating
    # frame_count to 50 when the animation is really just 2 frames.
    # Depth-layer bases have already been expanded into static layers above, so they
    # will not contribute numeric keys here.
    anim_nums = [
        k for fmap in layer_frames.values()
        for k in fmap
        if k is not None and sum(1 for kk in fmap if kk is not None) > 1
    ]
    if not anim_nums:
        # No truly animated layers; treat as static composite.
        return canvas_w, canvas_h, 1, list(layer_frames.keys()), layer_frames, 1

    min_frame    = min(anim_nums)
    max_frame    = max(anim_nums)
    frame_count  = max_frame - min_frame + 1
    frame_offset = min_frame  # 0 when sheet starts at _00, else 1

    # Preserve plist insertion order — that IS the intended bottom-to-top render order.
    layer_order = list(layer_frames.keys())
    return canvas_w, canvas_h, max(frame_count, 1), layer_order, layer_frames, frame_offset


def composite_sheet_frame(
    atlas: QImage, sprites: dict,
    canvas_w: int, canvas_h: int,
    layer_order: list, layer_frames: dict,
    frame_idx: int, frame_offset: int = 1,
) -> "QPixmap | None":
    """Composite one animation frame (0-based index)."""
    frame_num = frame_idx + frame_offset

    canvas = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    for base in layer_order:
        fmap = layer_frames[base]
        if frame_num in fmap:
            sprite_name = fmap[frame_num]
        elif None in fmap:
            sprite_name = fmap[None]        # static layer (no numeric suffix)
        else:
            avail = sorted(k for k in fmap if k is not None and k <= frame_num)
            if not avail:
                avail = sorted(k for k in fmap if k is not None)
            sprite_name = fmap[avail[-1]]

        sx, sy, sw, sh, ox, oy, ow, oh, rotated = sprites[sprite_name]
        px = round((canvas_w - sw) / 2 + ox)
        py = round((canvas_h - sh) / 2 - oy)

        if rotated:
            tile = atlas.copy(QRect(round(sx), round(sy), round(sh), round(sw)))
            tile = tile.transformed(QTransform().rotate(-90))
            p.drawImage(QRect(px, py, round(sw), round(sh)), tile)
        else:
            p.drawImage(QRect(px, py, round(sw), round(sh)),
                        atlas, QRect(round(sx), round(sy), round(sw), round(sh)))

    p.end()
    return QPixmap.fromImage(canvas)
