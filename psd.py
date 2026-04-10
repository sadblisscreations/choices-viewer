import io
from pathlib import Path

import numpy as np
from PIL import Image as PILImage

from PyQt6.QtCore import QBuffer
from PyQt6.QtGui import QImage, QRect, QTransform

from .plist_parser import parse_plist
from .compositing import CUSTOM_LAYER_ORDER, SLOT_LABELS, LAYER_ORDER


def _qimage_to_rgba(qimg: QImage) -> np.ndarray:
    """Convert a QImage to an RGBA numpy array (H × W × 4, uint8)."""
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.ReadWrite)
    qimg.save(buf, "PNG")
    buf.seek(0)
    pil = PILImage.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")
    return np.array(pil)


def _psd_layer(name: str, qimg: QImage, top: int, left: int):
    """Return a pytoshop nested_layers.Image for one sprite tile."""
    from pytoshop.user import nested_layers
    arr  = _qimage_to_rgba(qimg)
    h, w = arr.shape[:2]
    return nested_layers.Image(
        name=name,
        channels={
            -1: np.ascontiguousarray(arr[:, :, 3]),  # transparency
             0: np.ascontiguousarray(arr[:, :, 0]),  # R
             1: np.ascontiguousarray(arr[:, :, 1]),  # G
             2: np.ascontiguousarray(arr[:, :, 2]),  # B
        },
        top=top, left=left, bottom=top + h, right=left + w,
        visible=True,
    )


def write_layered_psd(groups: list, canvas_w: int, canvas_h: int, path: str):
    """
    Write a layered PSD file.

    groups: [(group_name, [(layer_name, QImage, px, py)]), ...]
            If groups has only one entry whose name is '', layers are written flat.
    """
    import pytoshop
    from pytoshop.user import nested_layers
    from pytoshop.enums import Compression, ColorMode

    psd_top = []
    for g_name, layer_list in groups:
        psd_layers = [_psd_layer(ln, img, py, px) for ln, img, px, py in layer_list]
        if g_name:
            psd_top.append(nested_layers.Group(name=g_name, layers=psd_layers, closed=False))
        else:
            psd_top.extend(psd_layers)

    psd = nested_layers.nested_layers_to_psd(
        psd_top, color_mode=ColorMode.rgb, compression=Compression.raw
    )
    psd.height = canvas_h
    psd.width  = canvas_w
    with open(path, "wb") as f:
        psd.write(f)


def extract_sprite_layers(atlas_path: Path, sprites: dict, emotion: str):
    """
    Return (canvas_w, canvas_h, [(layer_name, QImage_tile, px, py)]) for one emotion.
    Used by the Characters tab PSD save path.
    """
    layer_keys = [t.replace("{e}", emotion) for t in LAYER_ORDER
                  if t.replace("{e}", emotion) in sprites]
    if not layer_keys:
        return 0, 0, []

    atlas  = QImage(str(atlas_path))
    max_w  = max_h = 0
    for lk in layer_keys:
        _, _, _, _, _, _, ow, oh, _ = sprites[lk]
        max_w = max(max_w, round(ow)); max_h = max(max_h, round(oh))

    result = []
    for lk in layer_keys:
        sx, sy, sw, sh, ox, oy, ow, oh, rotated = sprites[lk]
        px = round((ow - sw) / 2 + ox)
        py = round((oh - sh) / 2 - oy)
        if rotated:
            tile = atlas.copy(QRect(round(sx), round(sy), round(sh), round(sw)))
            tile = tile.transformed(QTransform().rotate(-90))
        else:
            tile = atlas.copy(QRect(round(sx), round(sy), round(sw), round(sh)))
        name = lk.replace(".png", "").replace("FACE_", "Face: ").replace("_", " ").title()
        result.append((name, tile, px, py))

    return max_w, max_h, result


def extract_custom_layers(selections: dict, emotion: str):
    """
    Return (canvas_w, canvas_h, [(layer_name, QImage_tile, px, py)]).
    Used by the Custom tab PSD save path.
    """
    canvas_w = canvas_h = 0
    raw = []
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
        raw.append((slot, str(png_path), sx, sy, sw, sh, ox, oy, rotated))

    if not raw:
        return 0, 0, []

    result = []
    for slot, png_path, sx, sy, sw, sh, ox, oy, rotated in raw:
        atlas = QImage(png_path)
        px = round((canvas_w - sw) / 2 + ox)
        py = round((canvas_h - sh) / 2 - oy)
        if rotated:
            tile = atlas.copy(QRect(round(sx), round(sy), round(sh), round(sw)))
            tile = tile.transformed(QTransform().rotate(-90))
        else:
            tile = atlas.copy(QRect(round(sx), round(sy), round(sw), round(sh)))
        result.append((SLOT_LABELS.get(slot, slot.title()), tile, px, py))

    return canvas_w, canvas_h, result


def extract_sheet_frame_layers(
    atlas_path: Path, sprites: dict,
    canvas_w: int, canvas_h: int,
    layer_order: list, layer_frames: dict,
    frame_idx: int,
) -> list:
    """Return [(layer_name, QImage_tile, px, py)] for a single animation frame."""
    frame_num = frame_idx + 1
    atlas = QImage(str(atlas_path))
    result = []
    for base in layer_order:
        fmap = layer_frames[base]
        if frame_num in fmap:
            sprite_name = fmap[frame_num]
        elif 0 in fmap:
            sprite_name = fmap[0]
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
        else:
            tile = atlas.copy(QRect(round(sx), round(sy), round(sw), round(sh)))

        short = base.split("_")[-1] if "_" in base else base
        result.append((short.title(), tile, px, py))
    return result
