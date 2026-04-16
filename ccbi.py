"""
CCBI scene parser and particle renderer for Qt.
Based on the Cocos2d-x CCBReader binary format.
"""

import math
import random
import struct
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QImage, QPainter, QColor


# =================== PARSER ===================

class CCBReader:
    def __init__(self, data: bytes):
        self._bytes = data
        self._pos = 0
        self._bit = 0
        self._string_cache = []

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
                    if easing_type in (1, 2, 3, 4, 5, 6):
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

CANVAS_W, CANVAS_H = 960, 780


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

    bg_name = find_bg(ng)
    bg_raw, native_w, native_h = load_background(bg_name, bg_dir)

    is_wide = (native_w / native_h) > 1.2
    if is_wide:
        full_h = CANVAS_H
        full_w = int(CANVAS_H * native_w / native_h)
    else:
        ratio = native_w / native_h
        if ratio > CANVAS_W / CANVAS_H:
            full_w = CANVAS_W
            full_h = int(CANVAS_W / ratio)
        else:
            full_h = CANVAS_H
            full_w = int(CANVAS_H * ratio)

    bg = bg_raw.scaled(full_w, full_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

    ox = (CANVAS_W - full_w) // 2 if not is_wide else 0
    oy = (CANVAS_H - full_h) // 2

    design_h = native_h / 2
    ptf = full_h / design_h if design_h > 0 else 1.0

    cfgs = []
    extract_emitters(ng, cfgs)

    emitters = []
    for c in cfgs:
        pct_x = c.get("_abs_x", 50)
        pct_y = c.get("_abs_y", 50)
        if is_wide:
            sx = (pct_x / 100.0) * full_w
            sy = (1.0 - pct_y / 100.0) * full_h
        else:
            sx = ox + (pct_x / 100.0) * full_w
            sy = oy + (1.0 - pct_y / 100.0) * full_h
        emitters.append(Emitter(c, sx, sy, ptf))

    pan_max = max(0, full_w - CANVAS_W) if is_wide else 0

    return {
        "bg": bg,
        "emitters": emitters,
        "is_wide": is_wide,
        "pan_max": pan_max,
        "pan": 0,
        "full_w": full_w,
        "full_h": full_h,
        "ox": ox,
        "oy": oy,
        "seqs": [s["name"] for s in data["sequences"]],
        "_ccbi_path": ccbi_path,
        "_bg_dir": bg_dir,
        "_tex_dir": tex_dir,
    }


def render_scene_to_image(canvas: QImage, scene: dict, texcache: TextureCache) -> int:
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    canvas.fill(QColor(15, 15, 26))
    pan = scene["pan"]
    bg = scene["bg"]
    is_wide = scene["is_wide"]
    ox = scene["ox"]
    oy = scene["oy"]

    if is_wide:
        painter.drawImage(-pan, 0, bg)
    else:
        painter.drawImage(ox, oy, bg)

    if is_wide:
        painter.setClipRect(0, 0, CANVAS_W, scene["full_h"])
    else:
        painter.setClipRect(ox, oy, scene["full_w"], scene["full_h"])

    total = 0
    for em in scene["emitters"]:
        for p in em.particles:
            if p.a < 0.01:
                continue
            sz = max(4, int(p.sz))
            sz = min(sz, 512)
            px = int(p.x) - pan if is_wide else int(p.x)
            py = int(p.y)
            hsz = sz // 2
            surf = texcache.get(em.tex, sz, p.r, p.g, p.b, p.a, em.additive)
            if surf:
                if em.additive:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
                painter.drawImage(px - hsz, py - hsz, surf)
                if em.additive:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        total += len(em.particles)

    painter.setClipping(False)
    painter.end()
    return total
