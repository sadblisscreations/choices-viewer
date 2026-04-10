import re
from pathlib import Path

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QTransform

from .plist_parser import parse_plist

# ── Character layer constants ─────────────────────────────────────────────────

LAYER_ORDER = ["HAIR_B.png", "BODY.png", "FACE_{e}.png", "HAIR_F.png", "PROP_F.png"]
EMOTIONS    = ["NEUTRAL", "HAPPY", "ANGRY", "SAD", "SURPRISED"]

# ── Custom character layer constants ──────────────────────────────────────────

# Bottom-to-top render order
CUSTOM_LAYER_ORDER = ["prop_b", "hair_b", "body", "clothing", "tattoo", "face", "hair_f", "hat_f", "prop_f", "acc"]
CUSTOM_OPTIONAL    = frozenset(["prop_b", "hat_f", "prop_f", "acc", "tattoo"])

SLOT_LABELS = {
    "prop_b":   "Prop Back",
    "body":     "Body / Skin",
    "face":     "Face",
    "hair_b":   "Hair Back",
    "hair_f":   "Hair Front",
    "clothing": "Clothing",
    "hat_f":    "Hat",
    "prop_f":   "Prop",
    "acc":      "Accessory",
    "tattoo":   "Tattoo",
}


# ── Character compositing ─────────────────────────────────────────────────────

def composite(atlas_path: Path, sprites: dict, emotion: str) -> "QPixmap | None":
    layers = [t.replace("{e}", emotion) for t in LAYER_ORDER if t.replace("{e}", emotion) in sprites]
    if not layers:
        return None
    atlas = QImage(str(atlas_path))
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

        key = f"{emotion}.png" if slot == "face" else "NEUTRAL.png"
        if key not in sprites:
            key = "NEUTRAL.png"
        if key not in sprites:
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
        atlas = QImage(png_path)
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

def analyze_spritesheet(sprites: dict) -> tuple:
    """
    Group sprites into animation layers by stripping trailing _NN frame numbers.
    Returns (canvas_w, canvas_h, frame_count, layer_order, layer_frames)
      layer_frames: {base_name: {frame_num: sprite_key}}
      frame_count : max frame number (>=1)
    """
    canvas_w = canvas_h = 0
    for sx, sy, sw, sh, ox, oy, ow, oh, rot in sprites.values():
        canvas_w = max(canvas_w, round(ow))
        canvas_h = max(canvas_h, round(oh))

    layer_frames: dict = {}
    for name in sprites:
        m = re.match(r"^(.+?)_(\d+)\.png$", name)
        if m:
            base, num = m.group(1), int(m.group(2))
        else:
            base = name
            num  = 0
        layer_frames.setdefault(base, {})[num] = name

    frame_count = max(
        (max(fmap.keys()) for fmap in layer_frames.values()),
        default=1,
    )
    # Preserve plist insertion order — that IS the intended bottom-to-top render order.
    layer_order = list(layer_frames.keys())
    return canvas_w, canvas_h, max(frame_count, 1), layer_order, layer_frames


def composite_sheet_frame(
    atlas: QImage, sprites: dict,
    canvas_w: int, canvas_h: int,
    layer_order: list, layer_frames: dict,
    frame_idx: int,
) -> "QPixmap | None":
    """Composite one animation frame (0-based index)."""
    frame_num = frame_idx + 1          # sprites are 1-based (0 = static)

    canvas = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    for base in layer_order:
        fmap = layer_frames[base]
        if frame_num in fmap:
            sprite_name = fmap[frame_num]
        elif 0 in fmap:
            sprite_name = fmap[0]           # static layer
        else:
            avail = sorted(k for k in fmap if k <= frame_num)
            if not avail:
                avail = sorted(fmap)
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
