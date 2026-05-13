"""
CCBI scene parser and particle renderer for Qt.
Based on the Cocos2d-x CCBReader binary format.
"""

import math
import random
import struct
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image
from PyQt6.QtCore import Qt, QRect, QPointF
from PyQt6.QtGui import QImage, QPainter, QColor, QTransform

from .plist_parser import parse_plist


# =================== PARSER ===================

class CCBReader:
    def __init__(self, data: bytes):
        self._bytes = data
        self._pos = 0
        self._bit = 0
        self._string_cache = []
        self._js_controlled = False

    def read_byte(self):
        b = self._bytes[self._pos]
        self._pos += 1
        return b

    def read_bool(self):
        return self.read_byte() != 0

    def get_bit(self):
        byte = self._bytes[self._pos]
        bit = bool(byte & (1 << self._bit))
        self._bit += 1
        if self._bit >= 8:
            self._bit = 0
            self._pos += 1
        return bit

    def align_bits(self):
        if self._bit:
            self._bit = 0
            self._pos += 1

    def read_int(self, signed=False):
        num_bits = 0
        while not self.get_bit():
            num_bits += 1
        current = 0
        for a in range(num_bits - 1, -1, -1):
            if self.get_bit():
                current |= 1 << a
        current |= 1 << num_bits
        if signed:
            s = current % 2
            num = current // 2 if s else -(current // 2)
        else:
            num = current - 1
        self.align_bits()
        return num

    def read_float(self):
        ftype = self.read_byte()
        if ftype == 0:
            return 0.0
        if ftype == 1:
            return 1.0
        if ftype == 2:
            return -1.0
        if ftype == 3:
            return 0.5
        if ftype == 4:
            return float(self.read_int(signed=True))
        if ftype == 5:
            val = struct.unpack_from("<f", self._bytes, self._pos)[0]
            self._pos += 4
            return val
        return 0.0

    def read_utf8(self):
        b0 = self.read_byte()
        b1 = self.read_byte()
        num_bytes = (b0 << 8) | b1
        s = self._bytes[self._pos : self._pos + num_bytes].decode("utf-8", errors="replace")
        self._pos += num_bytes
        return s

    def read_cached_string(self):
        n = self.read_int(signed=False)
        if n < len(self._string_cache):
            return self._string_cache[n]
        return f"<str_{n}>"

    def read_header(self):
        magic = self._bytes[0:4]
        if magic != b"ibcc":
            raise ValueError(f"Bad magic: {magic}")
        self._pos = 4
        self._bit = 0
        version = self.read_int(signed=False)
        js_controlled = self.read_bool()
        self._js_controlled = js_controlled
        return version, js_controlled

    def read_string_cache(self):
        num_strings = self.read_int(signed=False)
        self._string_cache = [self.read_utf8() for _ in range(num_strings)]
        return self._string_cache

    def read_sequences(self):
        sequences = []
        for _ in range(self.read_int(signed=False)):
            seq = {
                "duration": self.read_float(),
                "name": self.read_cached_string(),
                "id": self.read_int(signed=False),
                "chained_id": self.read_int(signed=True),
            }
            for _ in range(self.read_int(signed=False)):
                self.read_float()
                self.read_cached_string()
                self.read_int(signed=False)
            for _ in range(self.read_int(signed=False)):
                self.read_float()
                self.read_cached_string()
                self.read_float()
                self.read_float()
                self.read_float()
            sequences.append(seq)
        autoplay_id = self.read_int(signed=True)
        return sequences, autoplay_id

    def read_keyframe_value(self, prop_type):
        if prop_type == 9:
            return self.read_bool()
        if prop_type == 12:
            return self.read_byte()
        if prop_type == 13:
            return (self.read_byte(), self.read_byte(), self.read_byte())
        if prop_type == 5:
            return self.read_float()
        if prop_type in (4, 0, 27):
            return (self.read_float(), self.read_float())
        if prop_type == 10:
            return (self.read_cached_string(), self.read_cached_string())
        return None

    def read_node_graph(self):
        node = {"class": self.read_cached_string()}
        if self._js_controlled:
            node["js_name"] = self.read_cached_string()
        assign_type = self.read_int(signed=False)
        if assign_type != 0:
            node["member_var"] = self.read_cached_string()
            node["member_var_type"] = assign_type

        node["animations"] = {}
        for _ in range(self.read_int(signed=False)):
            seq_id = self.read_int(signed=False)
            seq_props = {}
            for _ in range(self.read_int(signed=False)):
                prop_name = self.read_cached_string()
                prop_type = self.read_int(signed=False)
                keyframes = []
                for _ in range(self.read_int(signed=False)):
                    kf = {"time": self.read_float()}
                    easing_type = self.read_int(signed=False)
                    kf["easing"] = easing_type
                    if easing_type in (2, 3, 4, 5, 6, 7):
                        kf["easing_opt"] = self.read_float()
                    kf["value"] = self.read_keyframe_value(prop_type)
                    keyframes.append(kf)
                seq_props[prop_name] = {"type": prop_type, "keyframes": keyframes}
            node["animations"][seq_id] = seq_props

        node["properties"] = {}
        num_regular = self.read_int(signed=False)
        num_extra = self.read_int(signed=False)
        for _ in range(num_regular + num_extra):
            prop_type = self.read_int(signed=False)
            prop_name = self.read_cached_string()
            platform = self.read_byte()
            node["properties"][prop_name] = {
                "type": prop_type,
                "value": self._read_prop_value(prop_type),
            }

        node["children"] = [self.read_node_graph() for _ in range(self.read_int(signed=False))]
        return node

    def _read_prop_value(self, prop_type):
        if prop_type == 0:
            return {"x": self.read_float(), "y": self.read_float(), "type": self.read_int(signed=False)}
        if prop_type == 1:
            return {"w": self.read_float(), "h": self.read_float(), "type": self.read_int(signed=False)}
        if prop_type in (2, 3):
            return (self.read_float(), self.read_float())
        if prop_type == 4:
            return {"x": self.read_float(), "y": self.read_float(), "type": self.read_int(signed=False)}
        if prop_type == 5:
            return self.read_float()
        if prop_type == 6:
            return self.read_int(signed=True)
        if prop_type == 7:
            return self.read_float()
        if prop_type == 8:
            return (self.read_float(), self.read_float())
        if prop_type == 9:
            return self.read_bool()
        if prop_type == 10:
            return {"sheet": self.read_cached_string(), "sprite": self.read_cached_string()}
        if prop_type == 11:
            return self.read_cached_string()
        if prop_type == 12:
            return self.read_byte()
        if prop_type == 13:
            return (self.read_byte(), self.read_byte(), self.read_byte())
        if prop_type == 14:
            return {
                "color": (self.read_float(), self.read_float(), self.read_float(), self.read_float()),
                "variance": (self.read_float(), self.read_float(), self.read_float(), self.read_float()),
            }
        if prop_type == 15:
            return (self.read_bool(), self.read_bool())
        if prop_type == 16:
            return (self.read_int(signed=False), self.read_int(signed=False))
        if prop_type in (17, 18, 19):
            return self.read_cached_string()
        if prop_type == 20:
            return self.read_int(signed=True)
        if prop_type == 21:
            return {"name": self.read_cached_string(), "target": self.read_int(signed=False)}
        if prop_type == 22:
            return {"file": self.read_cached_string(), "name": self.read_cached_string()}
        if prop_type in (23, 24):
            return self.read_cached_string()
        if prop_type == 25:
            return {"name": self.read_cached_string(), "target": self.read_int(signed=False), "events": self.read_int(signed=False)}
        if prop_type == 26:
            return {"value": self.read_float(), "type": self.read_int(signed=False)}
        if prop_type == 27:
            return (self.read_float(), self.read_float())
        raise ValueError(f"Unknown property type: {prop_type}")

    def parse(self):
        version, js_controlled = self.read_header()
        strings = self.read_string_cache()
        sequences, autoplay_id = self.read_sequences()
        node_graph = self.read_node_graph()
        return {
            "version": version,
            "js_controlled": js_controlled,
            "strings": strings,
            "sequences": sequences,
            "autoplay_id": autoplay_id,
            "node_graph": node_graph,
        }


def parse_ccbi_file(filepath: Path) -> dict:
    with open(filepath, "rb") as f:
        data = f.read()
    return CCBReader(data).parse()


# =================== NODE TREE HELPERS ===================

def _get_pos(props):
    pos = props.get("position", {}).get("value", {})
    if isinstance(pos, dict):
        return pos.get("x", 0), pos.get("y", 0), pos.get("type", 0)
    return 0, 0, 0


def _get_size(props):
    sz = props.get("contentSize", {}).get("value", {})
    if isinstance(sz, dict):
        return sz.get("w", 0), sz.get("h", 0), sz.get("type", 0)
    return 0, 0, 0


def _get_anchor(props):
    a = props.get("anchorPoint", {}).get("value", None)
    return a if isinstance(a, tuple) and len(a) == 2 else (0.5, 0.5)


def extract_emitters(node, out, parent_ox=0, parent_oy=0, parent_w=100, parent_h=100):
    cls = node.get("class", "")
    props = node.get("properties", {})
    if "CCBFile" in cls:
        return
    vis = props.get("visible", {})
    if isinstance(vis, dict) and vis.get("value") is False:
        return

    if "Particle" in cls:
        cfg = {k: v["value"] for k, v in props.items()}
        cfg["_cls"] = cls
        cfg["_node_id"] = node.get("_node_id")
        px, py, pt = _get_pos(props)
        if pt == 4:
            cfg["_abs_x"] = parent_ox + (px / 100.0) * parent_w
            cfg["_abs_y"] = parent_oy + (py / 100.0) * parent_h
        else:
            cfg["_abs_x"] = px
            cfg["_abs_y"] = py
        out.append(cfg)
        return

    px, py, pt = _get_pos(props)
    sw, sh, st = _get_size(props)
    ax, ay = _get_anchor(props)

    if sw > 0 or sh > 0:
        if st == 1:
            node_w = (sw / 100.0) * parent_w
            node_h = (sh / 100.0) * parent_h
        else:
            node_w = sw / 100.0 * parent_w if parent_w > 0 else sw
            node_h = sh / 100.0 * parent_h if parent_h > 0 else sh
        if pt == 4:
            anc_x = parent_ox + (px / 100.0) * parent_w
            anc_y = parent_oy + (py / 100.0) * parent_h
        else:
            anc_x = px
            anc_y = py
        child_ox = anc_x - ax * node_w
        child_oy = anc_y - ay * node_h
    else:
        child_ox = parent_ox
        child_oy = parent_oy
        node_w = parent_w
        node_h = parent_h

    for c in node.get("children", []):
        extract_emitters(c, out, child_ox, child_oy, node_w, node_h)


def _assign_node_ids(node: dict, counter: list[int] | None = None) -> None:
    if counter is None:
        counter = [0]
    node["_node_id"] = counter[0]
    counter[0] += 1
    for child in node.get("children", []):
        _assign_node_ids(child, counter)


def _animated_sequence_ids(node: dict, out: set[int] | None = None) -> set[int]:
    if out is None:
        out = set()
    for seq_id, props in node.get("animations", {}).items():
        if props:
            out.add(seq_id)
    for child in node.get("children", []):
        _animated_sequence_ids(child, out)
    return out


def find_bg(node):
    props = node.get("properties", {})
    df = props.get("displayFrame", {})
    if isinstance(df, dict):
        sp = df.get("value", {})
        if isinstance(sp, dict):
            s = sp.get("sprite", "")
            if s and ".jpg" in s:
                return s
    for c in node.get("children", []):
        r = find_bg(c)
        if r:
            return r
    return None


# =================== SPRITE ASSETS ===================

def _assets_root(ccbi_path: Path) -> Path:
    parts = [p.lower() for p in ccbi_path.parts]
    if "assets" in parts:
        return Path(*ccbi_path.parts[:parts.index("assets") + 1])
    return ccbi_path.parent.parent


@lru_cache(maxsize=16)
def _name_index(root_s: str) -> dict[str, list[Path]]:
    root = Path(root_s)
    out: dict[str, list[Path]] = {}
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".plist", ".png", ".jpg", ".jpeg"}:
            out.setdefault(p.name.lower(), []).append(p)
    return out


def _find_name(root: Path, name: str, suffix: str | None = None) -> Path | None:
    hits = _name_index(str(root.resolve())).get(Path(name).name.lower(), [])
    if suffix:
        hits = [p for p in hits if p.suffix.lower() == suffix.lower()]
    if not hits:
        return None

    def score(path: Path):
        rel = str(path.relative_to(root)).lower().replace("\\", "/")
        s = 0
        if "/large/" in rel:
            s -= 10
        if "ccbi_spritesheets" in rel:
            s -= 6
        if "backgrounds" in rel:
            s -= 5
        if "loading_screen_images_240/2x" in rel:
            s -= 4
        if "ccbi_images/2x" in rel:
            s -= 3
        return s, rel

    return sorted(hits, key=score)[0]


class FrameAsset:
    __slots__ = ["image", "w", "h", "source_w", "source_h", "trimmed", "file"]

    def __init__(self, image: QImage, w: int, h: int, source_w: int, source_h: int, file: str, trimmed: bool = False):
        self.image = image
        self.w = max(1, w)
        self.h = max(1, h)
        self.source_w = max(1, source_w)
        self.source_h = max(1, source_h)
        self.trimmed = trimmed
        self.file = file


def _qimage_from_pil(img: Image.Image) -> QImage:
    img = img.convert("RGBA")
    raw = img.tobytes("raw", "RGBA")
    q = QImage(raw, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888)
    return q.copy()


def _plist_texture_path(plist: Path) -> Path | None:
    for suffix in (".png", ".jpg", ".jpeg"):
        candidate = plist.with_suffix(suffix)
        try:
            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate
        except OSError:
            continue
    return None


def _atlas_frame_image(plist: Path, sprite: str, trim: bool = False) -> FrameAsset | None:
    frames = parse_plist(plist)
    frame = frames.get(Path(sprite).name)
    if frame is None and not frames:
        frame = _infer_empty_frame(plist, sprite)
    if frame is None:
        return None

    sx, sy, sw, sh, ox, oy, ow, oh, rotated = frame
    atlas_path = _plist_texture_path(plist)
    if atlas_path is None:
        return None
    atlas = Image.open(atlas_path).convert("RGBA")
    if rotated:
        crop = atlas.crop((round(sx), round(sy), round(sx + sh), round(sy + sw))).transpose(Image.Transpose.ROTATE_90)
    else:
        crop = atlas.crop((round(sx), round(sy), round(sx + sw), round(sy + sh)))

    if trim:
        return FrameAsset(_qimage_from_pil(crop), crop.width, crop.height, round(ow), round(oh), sprite, True)

    canvas = Image.new("RGBA", (max(1, round(ow)), max(1, round(oh))), (0, 0, 0, 0))
    left = round((canvas.width - crop.width) / 2 + ox)
    top = round((canvas.height - crop.height) / 2 - oy)
    canvas.alpha_composite(crop, (left, top))
    return FrameAsset(_qimage_from_pil(canvas), canvas.width, canvas.height, canvas.width, canvas.height, sprite)


@lru_cache(maxsize=256)
def _infer_empty_frame(plist: Path, sprite: str):
    texture = _plist_texture_path(plist)
    if texture is None:
        return None
    alpha = Image.open(texture).convert("RGBA").getchannel("A")
    w, h = alpha.size
    px = alpha.load()
    seen: set[tuple[int, int]] = set()
    comps: list[tuple[int, int, int, int, int]] = []
    for y in range(h):
        for x in range(w):
            if not px[x, y] or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            x1 = x2 = x
            y1 = y2 = y
            count = 0
            while stack:
                cx, cy = stack.pop()
                count += 1
                x1, x2 = min(x1, cx), max(x2, cx)
                y1, y2 = min(y1, cy), max(y2, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            if count >= 20:
                comps.append((x1, y1, x2 + 1, y2 + 1, count))
    if not comps:
        return None

    lower = sprite.lower()
    def area(c): return (c[2] - c[0]) * (c[3] - c[1])
    chosen = None
    if "banner" in lower:
        chosen = max((c for c in comps if (c[0] + c[2]) / 2 > w * 0.55), key=area, default=None)
    elif "sparkle" in lower:
        mid = [c for c in comps if (c[0] + c[2]) / 2 < w * 0.65 and h * 0.30 < (c[1] + c[3]) / 2 < h * 0.62]
        if mid:
            chosen = (min(c[0] for c in mid), min(c[1] for c in mid), max(c[2] for c in mid), max(c[3] for c in mid), sum(c[4] for c in mid))
    elif "icon" in lower:
        chosen = max((c for c in comps if (c[0] + c[2]) / 2 < w * 0.65 and (c[1] + c[3]) / 2 > h * 0.45), key=area, default=None)
    elif "burst" in lower:
        chosen = max((c for c in comps if (c[0] + c[2]) / 2 < w * 0.7 and (c[1] + c[3]) / 2 < h * 0.40), key=area, default=None)
    if chosen is None:
        chosen = max(comps, key=area)

    x1, y1, x2, y2, _ = chosen
    if "banner" in lower and (y2 - y1) > (x2 - x1) * 2:
        visual_w, visual_h = y2 - y1, x2 - x1
        return (x1, y1, visual_w, visual_h, 0.0, (2048 - visual_h) / 2 - 2.0, 1688.0, 2048.0, True)
    ow = 1688.0 if h >= 1024 else float(x2 - x1)
    oh = 2048.0 if h >= 1024 else float(y2 - y1)
    return (x1, y1, x2 - x1, y2 - y1, x1 - (ow - (x2 - x1)) / 2, (oh - (y2 - y1)) / 2 - y1, ow, oh, False)


def _direct_image(root: Path, name: str) -> FrameAsset | None:
    path = _find_name(root, name)
    if not path or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return None
    img = QImage(str(path))
    if img.isNull():
        return None
    return FrameAsset(img, img.width(), img.height(), img.width(), img.height(), name)


def _sprite_key(value: dict | None) -> str:
    if not isinstance(value, dict):
        return ""
    return f'{value.get("sheet", "")}|{value.get("sprite", "") or value.get("file", "")}'


def _sprite_value(node: dict) -> dict | None:
    props = node.get("properties", {})
    for name in ("displayFrame", "spriteFrame", "normalSpriteFrame"):
        val = props.get(name, {}).get("value") if isinstance(props.get(name), dict) else None
        if isinstance(val, dict) and (val.get("sprite") or val.get("file")):
            return val
    return None


def _collect_sprites(node: dict, out: dict[str, dict]):
    val = _sprite_value(node)
    if val:
        out[_sprite_key(val)] = val
    tex = node.get("properties", {}).get("texture", {})
    if isinstance(tex, dict) and isinstance(tex.get("value"), str) and tex["value"]:
        val = {"sheet": "", "sprite": tex["value"]}
        out[_sprite_key(val)] = val
    for anim in node.get("animations", {}).values():
        for prop in anim.values():
            if prop.get("type") == 10:
                for key in prop.get("keyframes", []):
                    v = key.get("value")
                    if isinstance(v, tuple):
                        val = {"sheet": v[0], "sprite": v[1]}
                        out[_sprite_key(val)] = val
    for child in node.get("children", []):
        _collect_sprites(child, out)


def _resolve_assets(root: Path, ccbi_path: Path, node: dict) -> dict[str, FrameAsset]:
    values: dict[str, dict] = {}
    _collect_sprites(node, values)
    assets: dict[str, FrameAsset] = {}
    for key, val in values.items():
        sheet = val.get("sheet", "")
        sprite = val.get("sprite", "") or val.get("file", "")
        asset = None
        if sheet:
            plist = _find_name(root, sheet, ".plist")
            if plist:
                low_sheet = sheet.lower()
                low_sprite = sprite.lower()
                trim = low_sheet.startswith("bg_overlay_regular_") and "_spell" in low_sheet and "_spell_icon" in low_sprite
                asset = _atlas_frame_image(plist, sprite, trim)
        if asset is None and sprite:
            asset = _direct_image(root, sprite)
        if asset is not None:
            assets[key] = asset
    return assets


# =================== TEXTURE CACHE ===================

class TextureCache:
    QSTEPS = 16

    def __init__(self, tex_dir: Path):
        self.tex_dir = tex_dir
        self.raw: dict[str, QImage] = {}
        self._cache: dict[tuple, QImage] = {}

    def _q(self, v: float) -> int:
        return max(0, min(self.QSTEPS, int(v * self.QSTEPS + 0.5)))

    def _load(self, name: str) -> QImage:
        if name not in self.raw:
            path = self.tex_dir / name
            if path.exists():
                self.raw[name] = QImage(str(path))
            else:
                self.raw[name] = self._fallback(64)
        return self.raw[name]

    def _fallback(self, size: int) -> QImage:
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = cy = size // 2
        for r in range(cx, 0, -1):
            t = r / cx
            alpha = int(255 * t * t)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, alpha))
            p.drawEllipse(QPointF(cx, cy), r, r)
        p.end()
        return img

    def get(self, name: str, size: int, r: float, g: float, b: float, a: float, additive: bool) -> "QImage | None":
        if a < 0.01:
            return None
        qr, qg, qb, qa = self._q(r), self._q(g), self._q(b), self._q(a)
        key = (name, size, qr, qg, qb, qa, additive)
        if key not in self._cache:
            raw = self._load(name)
            self._cache[key] = _tint_image(raw, size, r, g, b, a, additive)
        return self._cache[key]


def _tint_image(img: QImage, size: int, r: float, g: float, b: float, a: float, additive: bool) -> QImage:
    scaled = img.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    scaled = scaled.convertToFormat(QImage.Format.Format_ARGB32)
    ptr = scaled.constBits()
    ptr.setsize(scaled.sizeInBytes())
    arr = np.frombuffer(ptr, np.uint8).reshape(scaled.height(), scaled.width(), 4).copy()

    tex_a = arr[:, :, 3].astype(np.float32)

    if additive:
        factor_r = r * a * tex_a / 255.0
        factor_g = g * a * tex_a / 255.0
        factor_b = b * a * tex_a / 255.0
        arr[:, :, 2] = np.clip(arr[:, :, 2].astype(np.float32) * factor_r, 0, 255).astype(np.uint8)
        arr[:, :, 1] = np.clip(arr[:, :, 1].astype(np.float32) * factor_g, 0, 255).astype(np.uint8)
        arr[:, :, 0] = np.clip(arr[:, :, 0].astype(np.float32) * factor_b, 0, 255).astype(np.uint8)
        arr[:, :, 3] = 255
    else:
        arr[:, :, 2] = np.clip(arr[:, :, 2].astype(np.float32) * r, 0, 255).astype(np.uint8)
        arr[:, :, 1] = np.clip(arr[:, :, 1].astype(np.float32) * g, 0, 255).astype(np.uint8)
        arr[:, :, 0] = np.clip(arr[:, :, 0].astype(np.float32) * b, 0, 255).astype(np.uint8)
        arr[:, :, 3] = np.clip(tex_a * a, 0, 255).astype(np.uint8)

    h, w = arr.shape[:2]
    result = QImage(arr.data, w, h, w * 4, QImage.Format.Format_ARGB32)
    return result.copy()


# =================== PARTICLE SYSTEM ===================

class Particle:
    __slots__ = ["x", "y", "vx", "vy", "life", "tl", "sz", "esz", "r", "g", "b", "a"]


def _clamp(v):
    return max(0.0, min(1.0, v))


def _vary(b, v):
    return b + random.uniform(-v, v)


def _fv(val):
    if isinstance(val, tuple) and len(val) == 2:
        return val[0], val[1]
    if isinstance(val, (int, float)):
        return val, 0
    return 0, 0


class Emitter:
    def __init__(self, cfg, sx, sy, ptf):
        self.x = sx
        self.y = sy
        sc = cfg.get("scale", {})
        scx = sc.get("x", 1) if isinstance(sc, dict) else 1
        scy = sc.get("y", 1) if isinstance(sc, dict) else 1
        abs_sx = abs(scx) if abs(scx) > 0.001 else 1.0
        abs_sy = abs(scy) if abs(scy) > 0.001 else 1.0
        uni_s = max(abs_sx, abs_sy)

        pv = cfg.get("posVar", (0, 0))
        self.pvx = pv[0] * abs_sx * ptf if isinstance(pv, tuple) else 0
        self.pvy = pv[1] * abs_sy * ptf if isinstance(pv, tuple) else 0

        a_val = cfg.get("angle", (90, 0))
        self.angle, self.avar = _fv(a_val)
        self.angle = math.radians(self.angle)
        self.avar = math.radians(self.avar)

        sp0, sp1 = _fv(cfg.get("speed", (0, 0)))
        self.spd = sp0 * uni_s * ptf
        self.spdv = sp1 * uni_s * ptf

        g = cfg.get("gravity", (0, 0))
        gx = g[0] if isinstance(g, tuple) else 0
        gy = g[1] if isinstance(g, tuple) else 0
        self.gx = gx * abs_sx * ptf
        self.gy = -gy * abs_sy * ptf

        self.life, self.lifev = _fv(cfg.get("life", (1, 0)))
        ss0, ss1 = _fv(cfg.get("startSize", (10, 0)))
        es0, es1 = _fv(cfg.get("endSize", (10, 0)))
        self.ssz = ss0 * uni_s * ptf
        self.sszv = ss1 * uni_s * ptf
        self.esz = es0 * uni_s * ptf
        self.eszv = es1 * uni_s * ptf

        self.sc_col = cfg.get("startColor", {"color": (1, 1, 1, 1), "variance": (0, 0, 0, 0)})
        self.ec_col = cfg.get("endColor", {"color": (1, 1, 1, 0), "variance": (0, 0, 0, 0)})
        mc = cfg.get("midColor", None)
        if isinstance(mc, dict):
            mc_c = mc.get("color", (0, 0, 0, 0))
            self.mc_col = mc if isinstance(mc_c, tuple) and len(mc_c) >= 4 and mc_c[3] <= 1.0 else None
        else:
            self.mc_col = None
        self.dur = cfg.get("duration", -1)
        self.maxp = min(cfg.get("totalParticles", 50), 300)
        self.rate = min(cfg.get("emissionRate", 10), 150)
        self.tex = cfg.get("texture", "")
        bf = cfg.get("blendFunc", (770, 771))
        self.additive = isinstance(bf, tuple) and bf[1] == 1
        self.particles = []
        self.ec = 0.0
        self.elapsed = 0.0
        self.active = True

    def update(self, dt):
        if not self.active:
            return
        self.elapsed += dt
        if self.dur > 0 and self.elapsed > self.dur:
            self.active = False
            return
        rate = 1.0 / max(self.rate, 0.001)
        self.ec += dt
        while self.ec > rate and len(self.particles) < self.maxp:
            self._emit()
            self.ec -= rate
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            t = 1.0 - p.life / p.tl
            p.vx += self.gx * dt
            p.vy += self.gy * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            if self.mc_col and t < 0.5:
                t2 = t * 2
                sc = self.sc_col.get("color", (1, 1, 1, 1))
                mc = self.mc_col.get("color", (1, 1, 1, 0.5))
                p.r = _clamp(sc[0] + (mc[0] - sc[0]) * t2)
                p.g = _clamp(sc[1] + (mc[1] - sc[1]) * t2)
                p.b = _clamp(sc[2] + (mc[2] - sc[2]) * t2)
                p.a = _clamp(sc[3] + (mc[3] - sc[3]) * t2)
            elif self.mc_col:
                t2 = (t - 0.5) * 2
                mc = self.mc_col.get("color", (1, 1, 1, 0.5))
                ec = self.ec_col.get("color", (1, 1, 1, 0))
                p.r = _clamp(mc[0] + (ec[0] - mc[0]) * t2)
                p.g = _clamp(mc[1] + (ec[1] - mc[1]) * t2)
                p.b = _clamp(mc[2] + (ec[2] - mc[2]) * t2)
                p.a = _clamp(mc[3] + (ec[3] - mc[3]) * t2)
            else:
                sc = self.sc_col.get("color", (1, 1, 1, 1))
                ec = self.ec_col.get("color", (1, 1, 1, 0))
                p.r = _clamp(sc[0] + (ec[0] - sc[0]) * t)
                p.g = _clamp(sc[1] + (ec[1] - sc[1]) * t)
                p.b = _clamp(sc[2] + (ec[2] - sc[2]) * t)
                p.a = _clamp(sc[3] + (ec[3] - sc[3]) * t)
            p.sz = max(0, p.sz + (p.esz - p.sz) * dt / max(p.life, 0.01))
            alive.append(p)
        self.particles = alive

    def _emit(self):
        p = Particle()
        p.x = self.x + random.uniform(-self.pvx, self.pvx)
        p.y = self.y + random.uniform(-self.pvy, self.pvy)
        a = self.angle + random.uniform(-self.avar, self.avar)
        s = _vary(self.spd, self.spdv)
        p.vx = math.cos(a) * s
        p.vy = -math.sin(a) * s
        p.life = max(0.1, _vary(self.life, self.lifev))
        p.tl = p.life
        p.sz = max(0.5, _vary(self.ssz, self.sszv))
        p.esz = max(0, _vary(self.esz, self.eszv))
        sc = self.sc_col.get("color", (1, 1, 1, 1))
        sv = self.sc_col.get("variance", (0, 0, 0, 0))
        p.r = _clamp(_vary(sc[0], sv[0]))
        p.g = _clamp(_vary(sc[1], sv[1]))
        p.b = _clamp(_vary(sc[2], sv[2]))
        p.a = _clamp(_vary(sc[3], sv[3]))
        self.particles.append(p)


# =================== SCENE RENDER ===================

CANVAS_W, CANVAS_H = 1688, 2048


def load_background(name, bg_dir: Path):
    if not name:
        img = QImage(640, 960, QImage.Format.Format_RGB32)
        img.fill(QColor(15, 15, 26))
        return img, 640, 960
    path = bg_dir / name
    if not path.exists():
        path = bg_dir / Path(name).name
    if path.exists():
        img = QImage(str(path))
        if not img.isNull():
            return img, img.width(), img.height()
    img = QImage(640, 960, QImage.Format.Format_RGB32)
    img.fill(QColor(15, 15, 26))
    return img, 640, 960


def setup_scene(ccbi_path: Path, bg_dir: Path, tex_dir: Path) -> dict:
    data = parse_ccbi_file(ccbi_path)
    ng = data["node_graph"]
    _assign_node_ids(ng)
    root = _assets_root(ccbi_path)
    assets = _resolve_assets(root, ccbi_path, ng)

    bg_name = find_bg(ng)
    bg_raw, native_w, native_h = load_background(bg_name, bg_dir)

    root_sprite = _sprite_value(ng)
    root_asset = assets.get(_sprite_key(root_sprite)) if root_sprite else None
    loading_bg = None
    rel_norm = str(ccbi_path).replace("\\", "/").lower()
    if "/loading_screens_ccbi_240/" in rel_norm:
        stem = ccbi_path.stem.lower()
        loading_bg = next((a for a in assets.values() if a.file.lower().startswith(stem) and a.file.lower().endswith((".jpg", ".png"))), None)

    if loading_bg:
        scene_w, scene_h = loading_bg.source_w, loading_bg.source_h
    elif root_asset:
        scene_w, scene_h = root_asset.source_w, root_asset.source_h
    elif assets:
        scene_w = max(a.source_w for a in assets.values())
        scene_h = max(a.source_h for a in assets.values())
    elif bg_name:
        scene_w, scene_h = native_w, native_h
    else:
        scene_w, scene_h = CANVAS_W, CANVAS_H

    scene_w = max(1, int(scene_w or CANVAS_W))
    scene_h = max(1, int(scene_h or CANVAS_H))
    canvas_w = max(scene_w, int(scene_h * 16 / 9))
    canvas_h = scene_h
    pad_x = (canvas_w - scene_w) // 2

    ptf = scene_h / max(1, native_h / 2)

    cfgs = []
    extract_emitters(ng, cfgs)

    emitters = []
    emitter_map = {}
    for c in cfgs:
        pct_x = c.get("_abs_x", 50)
        pct_y = c.get("_abs_y", 50)
        sx = pad_x + (pct_x / 100.0) * scene_w
        sy = (1.0 - pct_y / 100.0) * scene_h
        emitter = Emitter(c, sx, sy, ptf)
        emitters.append(emitter)
        emitter_map[c.get("_node_id")] = emitter

    seq_id = _choose_sequence(data["sequences"], data.get("autoplay_id", -1), ccbi_path)
    return {
        "bg": bg_raw,
        "emitters": emitters,
        "emitter_map": emitter_map,
        "ox": pad_x,
        "oy": 0,
        "seqs": [s["name"] for s in data["sequences"]],
        "sequences": data["sequences"],
        "animated_seq_ids": _animated_sequence_ids(ng),
        "_ccbi_path": ccbi_path,
        "_bg_dir": bg_dir,
        "_tex_dir": tex_dir,
        "root": root,
        "node_graph": ng,
        "assets": assets,
        "scene_w": scene_w,
        "scene_h": scene_h,
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "pad_x": pad_x,
        "seq_id": seq_id,
        "duration": _sequence_duration(data["sequences"], seq_id),
        "time": 0.0,
    }


def render_scene_to_image(canvas: QImage, scene: dict, texcache: TextureCache) -> int:
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    canvas.fill(QColor(15, 15, 26))
    render_scale = float(scene.get("render_scale", 1.0) or 1.0)
    painter.scale(render_scale, render_scale)
    screen_transform = painter.transform()
    view_x, view_w, view_pad = _viewport(scene)
    scene_shift = view_pad - view_x
    painter.save()
    painter.translate(scene_shift, scene.get("canvas_h", canvas.height()))
    painter.scale(1, -1)
    total = _draw_node(
        painter,
        scene["node_graph"],
        {"x": 0, "y": 0, "w": scene["scene_w"], "h": scene["scene_h"]},
        scene,
        texcache,
        scene_shift,
        screen_transform,
        scene.get("seq_id", 0),
        scene.get("time", 0.0),
        True,
        1.0,
    )
    painter.restore()

    painter.setClipping(False)
    painter.end()
    return total


def _viewport(scene: dict) -> tuple[int, int, int]:
    rel = str(scene.get("_ccbi_path", "")).lower().replace("\\", "/")
    root_props = _prop_values(scene.get("node_graph", {}))
    root_size = root_props.get("contentSize")
    regular_half = (
        "bg_overlay_regular_" in rel
        and isinstance(root_size, dict)
        and root_size.get("type") == 1
        and abs(float(root_size.get("w", 0)) - 50.0) < 0.01
    )
    if not regular_half:
        return 0, int(scene.get("scene_w", 0)), int(scene.get("pad_x", 0))

    half = max(1, int(scene.get("scene_w", 0)) // 2)
    seq_name = ""
    seq_id = scene.get("seq_id", 0)
    for seq in scene.get("sequences", []):
        if seq.get("id") == seq_id:
            seq_name = seq.get("name", "")
            break
    view_x = half if "RIGHT" in seq_name.upper() else 0
    view_pad = (int(scene.get("canvas_w", half)) - half) // 2
    return view_x, half, view_pad


def _choose_sequence(sequences: list, autoplay_id: int, ccbi_path: Path) -> int:
    if autoplay_id is not None and autoplay_id >= 0:
        return autoplay_id
    if not sequences:
        return 0
    if len(sequences) == 1:
        return sequences[0]["id"]
    candidates = [s for s in sequences if s.get("id") != 0]
    rel = str(ccbi_path).lower()
    looping = next((s for s in candidates if "LOOPING" in s.get("name", "")), None)
    fade_in = next((s for s in candidates if "FADEIN" in s.get("name", "")), None)
    active = sorted((s for s in candidates if "FADEOUT" not in s.get("name", "") and "POWER_OFF" not in s.get("name", "")), key=lambda s: s.get("duration", 0), reverse=True)
    chosen = ((looping if ("skill" in rel or "power" in rel) else None) or fade_in or (active[0] if active else None) or candidates[0] or sequences[0])
    return chosen["id"]


def _sequence_duration(sequences: list, seq_id: int) -> float:
    for seq in sequences:
        if seq.get("id") == seq_id:
            return max(0.001, float(seq.get("duration") or 1.0))
    return 1.0


def _prop_values(node: dict) -> dict:
    return {k: v.get("value") for k, v in node.get("properties", {}).items() if isinstance(v, dict)}


def _num(value, default=0.0) -> float:
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
    return float(default)


def _val_at(keys: list, t: float, base=None):
    if not keys:
        return base
    prev = keys[0]
    nxt = keys[-1]
    for key in keys:
        if key.get("time", 0) <= t:
            prev = key
        if key.get("time", 0) >= t:
            nxt = key
            break
    pv = prev.get("value")
    nv = nxt.get("value")
    if pv is None:
        return base
    if prev is nxt or nv is None or nxt.get("time") == prev.get("time"):
        return pv
    f = max(0.0, min(1.0, (t - prev.get("time", 0)) / (nxt.get("time", 0) - prev.get("time", 0))))
    if isinstance(pv, (int, float)) and isinstance(nv, (int, float)):
        return pv + (nv - pv) * f
    if (
        isinstance(pv, tuple) and isinstance(nv, tuple) and len(pv) >= 2
        and isinstance(pv[0], (int, float)) and isinstance(pv[1], (int, float))
        and isinstance(nv[0], (int, float)) and isinstance(nv[1], (int, float))
    ):
        return (pv[0] + (nv[0] - pv[0]) * f, pv[1] + (nv[1] - pv[1]) * f)
    return pv


def _anim_values(node: dict, seq_id: int, t: float) -> dict:
    out = {}
    base = _prop_values(node)
    for name, prop in node.get("animations", {}).get(seq_id, {}).items():
        val = _val_at(prop.get("keyframes", []), t)
        if name in {"displayFrame", "spriteFrame"} and isinstance(val, tuple):
            val = {"sheet": val[0], "sprite": val[1]}
        elif name == "position" and isinstance(val, tuple):
            typ = base.get("position", {}).get("type", 0) if isinstance(base.get("position"), dict) else 0
            val = {"x": val[0], "y": val[1], "type": typ}
        elif name == "scale" and isinstance(val, tuple):
            val = {"x": val[0], "y": val[1]}
        out[name] = val
    return out


def _node_size(asset: FrameAsset | None, props: dict, parent: dict) -> tuple[float, float]:
    cs = props.get("contentSize")
    if isinstance(cs, dict):
        w = _num(cs.get("w"), 0)
        h = _num(cs.get("h"), 0)
        typ = int(_num(cs.get("type"), 0))
        parent_w = _num(parent.get("w"), 0)
        parent_h = _num(parent.get("h"), 0)
        if typ == 1:
            w, h = parent_w * w / 100, parent_h * h / 100
        elif typ == 2:
            w, h = parent_w - w, parent_h - h
        elif typ == 3:
            w = parent_w * w / 100
        elif typ == 4:
            h = parent_h * h / 100
        return max(0.0, w), max(0.0, h)
    if asset:
        parent_w = _num(parent.get("w"), 0)
        parent_h = _num(parent.get("h"), 0)
        if parent.get("lazyScaleType") is not None and parent_w and parent_h:
            sx, sy = parent_w / asset.w, parent_h / asset.h
            scale = max(sx, sy) if int(_num(parent.get("lazyScaleType"), 0)) == 4 else min(sx, sy)
            return asset.w * scale, asset.h * scale
        return asset.w, asset.h
    return 0, 0


def _position(pos, parent: dict, is_root: bool) -> tuple[float, float]:
    if not isinstance(pos, dict):
        return (0, 0) if is_root else (0, 0)
    x, y, typ = _num(pos.get("x"), 0), _num(pos.get("y"), 0), int(_num(pos.get("type"), 0))
    parent_w = _num(parent.get("w"), 0)
    parent_h = _num(parent.get("h"), 0)
    if typ == 4:
        return parent_w * x / 100, parent_h * y / 100
    if typ == 1:
        return x, parent_h - y
    if typ == 2:
        return parent_w - x, parent_h - y
    if typ == 3:
        return parent_w - x, y
    return x, y


def _scale_value(scale):
    if isinstance(scale, dict):
        return _num(scale.get("x"), 1), _num(scale.get("y"), 1)
    if isinstance(scale, tuple) and len(scale) >= 2:
        return _num(scale[0], 1), _num(scale[1], 1)
    return 1, 1


def _anchor_value(anchor):
    if isinstance(anchor, tuple) and len(anchor) >= 2:
        return _num(anchor[0], 0.5), _num(anchor[1], 0.5)
    return 0.5, 0.5


def _draw_particles(painter: QPainter, emitter: Emitter, texcache: TextureCache, scene: dict, scene_shift: float, screen_transform, opacity: float) -> int:
    count = 0
    painter.save()
    painter.setTransform(screen_transform)
    for p in emitter.particles:
        if p.a < 0.01:
            continue
        sz = max(4, min(512, int(p.sz)))
        px = int(p.x + scene_shift - scene.get("pad_x", 0))
        py = int(p.y)
        hsz = sz // 2
        surf = texcache.get(emitter.tex, sz, p.r, p.g, p.b, p.a * opacity, emitter.additive)
        if surf:
            if emitter.additive:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            painter.drawImage(px - hsz, py - hsz, surf)
            if emitter.additive:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        count += 1
    painter.restore()
    return count


def _draw_node(painter: QPainter, node: dict, parent: dict, scene: dict, texcache: TextureCache, scene_shift: float, screen_transform, seq_id: int, t: float, is_root: bool = False, inherited_opacity: float = 1.0):
    base = _prop_values(node)
    anim = _anim_values(node, seq_id, t)
    props = {**base, **anim}
    if props.get("visible") is False:
        return 0

    sprite = props.get("displayFrame") or props.get("spriteFrame") or _sprite_value(node)
    asset = scene["assets"].get(_sprite_key(sprite))
    rel = str(scene.get("_ccbi_path", "")).lower()
    if asset and "bg_overlay_regular_" in rel and "_spell" in rel and "_spell_icon" in asset.file.lower():
        props["position"] = {"x": 59, "y": 58, "type": 4}
        props["anchorPoint"] = (0.5, 0.5)

    w, h = _node_size(asset, props, parent)
    pos = props.get("position")
    if pos is None:
        ax0, ay0 = _anchor_value(props.get("anchorPoint"))
        if is_root and asset and (abs(ax0) > 0.001 or abs(ay0) > 0.001):
            pos = {"x": 50, "y": 50, "type": 4}
        else:
            pos = {"x": 0, "y": 0, "type": 0}
    x, y = _position(pos, parent, is_root)
    sx, sy = _scale_value(props.get("scale"))
    ax, ay = _anchor_value(props.get("anchorPoint"))
    opacity = inherited_opacity * (max(0, min(255, _num(props.get("opacity"), 255))) / 255.0)

    painter.save()
    painter.translate(x, y)
    if props.get("rotation"):
        painter.rotate(-float(props["rotation"]))
    painter.scale(sx or 1, sy or 1)
    if not props.get("ignoreAnchorPointForPosition", False):
        painter.translate(-w * ax, -h * ay)

    if asset and opacity > 0.001:
        painter.save()
        painter.setOpacity(opacity)
        painter.translate(0, h)
        painter.scale(1, -1)
        painter.drawImage(QRect(0, 0, max(1, round(w)), max(1, round(h))), asset.image)
        painter.restore()

    total_particles = 0
    emitter = scene.get("emitter_map", {}).get(node.get("_node_id"))
    if emitter is not None and opacity > 0.001:
        total_particles += _draw_particles(painter, emitter, texcache, scene, scene_shift, screen_transform, opacity)

    child_parent = {"x": 0, "y": 0, "w": w or parent["w"], "h": h or parent["h"]}
    if node.get("class", "").lower() == "dklazysprite":
        child_parent["lazyScaleType"] = props.get("scaleType")
    child_opacity = opacity if props.get("cascadeOpacityEnabled") else inherited_opacity
    for child in node.get("children", []):
        total_particles += _draw_node(painter, child, child_parent, scene, texcache, scene_shift, screen_transform, seq_id, t, False, child_opacity)
    painter.restore()
    return total_particles
