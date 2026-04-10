import struct
from pathlib import Path


def _varint(data: bytes, pos: int):
    r, s = 0, 0
    while True:
        b = data[pos]; pos += 1
        r |= (b & 0x7F) << s; s += 7
        if not (b & 0x80): return r, pos


def _f32(data: bytes, pos: int):
    return struct.unpack_from("<f", data, pos)[0], pos + 4


def _read_floats(data: bytes, start: int, length: int) -> list:
    vals, pos, end = [], start, start + length
    while pos < end:
        try: tag, pos = _varint(data, pos)
        except IndexError: break
        wt = tag & 7
        if   wt == 5: v, pos = _f32(data, pos); vals.append(v)
        elif wt == 2: ln, pos = _varint(data, pos); pos += ln
        elif wt == 0: _, pos = _varint(data, pos)
        else: break
    return vals


def _parse_frame(data: bytes, start: int, length: int):
    name = src = off = orig = None
    rotated = False
    pos, end = start, start + length
    while pos < end:
        try: tag, pos = _varint(data, pos)
        except IndexError: break
        wt, fn = tag & 7, tag >> 3
        if wt == 2:
            ln, pos = _varint(data, pos)
            if   fn == 1: name = data[pos:pos+ln].decode("utf-8", errors="replace")
            elif fn == 2: src  = _read_floats(data, pos, ln)
            elif fn == 4: off  = _read_floats(data, pos, ln)
            elif fn == 5: orig = _read_floats(data, pos, ln)
            pos += ln
        elif wt == 0:
            val, pos = _varint(data, pos)
            if fn == 3: rotated = bool(val)
        elif wt == 5: pos += 4
        else: break
    return name, src, rotated, off, orig


def _parse_container(data: bytes, start: int, length: int) -> dict:
    sprites = {}
    pos, end = start, start + length
    while pos < end:
        try: tag, pos = _varint(data, pos)
        except IndexError: break
        wt, fn = tag & 7, tag >> 3
        if wt == 2:
            ln, pos = _varint(data, pos)
            if fn == 1:
                name, src, rotated, off, orig = _parse_frame(data, pos, ln)
                if name and src and len(src) >= 4:
                    ox, oy = (off[0],  off[1])  if off  and len(off)  >= 2 else (0.0, 0.0)
                    ow, oh = (orig[0], orig[1]) if orig and len(orig) >= 2 else (src[2], src[3])
                    sprites[name] = (src[0], src[1], src[2], src[3], ox, oy, ow, oh, rotated)
            pos += ln
        elif wt == 0: _, pos = _varint(data, pos)
        elif wt == 5: pos += 4
        else: break
    return sprites


def parse_plist(path: Path) -> dict:
    """Returns {sprite_name: (sx, sy, sw, sh, ox, oy, ow, oh, rotated)}."""
    data = path.read_bytes()
    sprites = {}
    pos = 0
    while pos < len(data):
        try: tag, pos = _varint(data, pos)
        except IndexError: break
        wt, fn = tag & 7, tag >> 3
        if wt == 2:
            ln, pos = _varint(data, pos)
            if fn == 4: sprites.update(_parse_container(data, pos, ln))
            pos += ln
        elif wt == 0: _, pos = _varint(data, pos)
        elif wt == 5: pos += 4
        else: break
    return sprites
