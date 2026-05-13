import re
from pathlib import Path

from PIL import Image as PILImage
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from .parsers.plist_parser import parse_plist
from .compositing import composite, composite_custom, composite_sheet_frame, EMOTIONS
from .psd import (
    write_layered_psd, extract_sprite_layers, extract_custom_layers,
    extract_sheet_frame_layers, _qimage_to_rgba,
)
from .parsers.ccbi_parser import CANVAS_W, CANVAS_H, setup_scene, render_scene_to_image, TextureCache


class LoadWorker(QThread):
    done = pyqtSignal(str, list)

    def __init__(self, name: str, png: Path, plist: Path):
        super().__init__()
        self._name, self._png, self._plist = name, png, plist

    def run(self):
        sprites = parse_plist(self._plist)
        results = []
        for emotion in EMOTIONS:
            has_body = "BODY.png" in sprites
            has_face = f"FACE_{emotion}.png" in sprites
            if emotion == "NEUTRAL" and not has_body:
                continue
            if emotion != "NEUTRAL" and not has_face:
                continue
            pix = composite(self._png, sprites, emotion)
            results.append((emotion, pix))
        self.done.emit(self._name, results)


class CustomLoadWorker(QThread):
    done = pyqtSignal(object)

    def __init__(self, selections: dict, emotion: str):
        super().__init__()
        self._selections = selections
        self._emotion    = emotion

    def run(self):
        pix = composite_custom(self._selections, self._emotion)
        self.done.emit(pix)


class SaveAllWorker(QThread):
    """Saves every character × every emotion to disk."""
    progress        = pyqtSignal(int, int, str)  # done, total, current_name
    finished_saving = pyqtSignal(int, int)        # saved_count, error_count

    def __init__(self, characters: list, out_dir: Path, fmt: str):
        super().__init__()
        self._chars     = characters
        self._out_dir   = out_dir
        self._fmt       = fmt          # "PNG", "JPEG", or "PSD"
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        is_psd = self._fmt == "PSD"
        ext    = "psd" if is_psd else ("png" if self._fmt == "PNG" else "jpg")
        total  = len(self._chars)
        saved  = errors = 0
        for i, (name, png, plist) in enumerate(self._chars):
            if self._cancelled:
                break
            self.progress.emit(i, total, name)
            try:
                sprites = parse_plist(plist)
                safe    = re.sub(r'[<>:"/\\|?*]', "_", name)

                if is_psd:
                    groups = []
                    cw = ch = 0
                    for emotion in EMOTIONS:
                        if emotion == "NEUTRAL" and "BODY.png" not in sprites:
                            continue
                        if emotion != "NEUTRAL" and f"FACE_{emotion}.png" not in sprites:
                            continue
                        w, h, ldata = extract_sprite_layers(png, sprites, emotion)
                        if ldata:
                            cw = max(cw, w); ch = max(ch, h)
                            groups.append((emotion.title(), ldata))
                    if groups:
                        write_layered_psd(groups, cw, ch, str(self._out_dir / f"{safe}.psd"))
                        saved += 1
                else:
                    char_dir = self._out_dir / safe
                    char_dir.mkdir(parents=True, exist_ok=True)
                    for emotion in EMOTIONS:
                        if emotion == "NEUTRAL" and "BODY.png" not in sprites:
                            continue
                        if emotion != "NEUTRAL" and f"FACE_{emotion}.png" not in sprites:
                            continue
                        pix = composite(png, sprites, emotion)
                        if pix and not pix.isNull():
                            pix.save(str(char_dir / f"{emotion.lower()}.{ext}"), self._fmt, 95)
                            saved += 1
            except Exception:
                errors += 1
        self.finished_saving.emit(saved, errors)


class SaveCustomEmotionsWorker(QThread):
    """Saves all emotion variants of the current custom build."""
    done = pyqtSignal(int)

    def __init__(self, selections: dict, out_dir: Path, fmt: str):
        super().__init__()
        self._selections = selections
        self._out_dir    = out_dir
        self._fmt        = fmt

    def run(self):
        is_psd = self._fmt == "PSD"
        ext    = "psd" if is_psd else ("png" if self._fmt == "PNG" else "jpg")
        saved  = 0
        if is_psd:
            groups = []
            cw = ch = 0
            for emotion in EMOTIONS:
                w, h, ldata = extract_custom_layers(self._selections, emotion)
                if ldata:
                    cw = max(cw, w); ch = max(ch, h)
                    groups.append((emotion.title(), ldata))
            if groups:
                write_layered_psd(groups, cw, ch, str(self._out_dir / "all_emotions.psd"))
                saved = len(groups)
        else:
            for emotion in EMOTIONS:
                pix = composite_custom(self._selections, emotion)
                if pix and not pix.isNull():
                    pix.save(str(self._out_dir / f"{emotion.lower()}.{ext}"), self._fmt, 95)
                    saved += 1
        self.done.emit(saved)


class GifSaveWorker(QThread):
    done = pyqtSignal(str)   # path on success, "" on error

    def __init__(self, atlas_path: Path, sprites: dict,
                 canvas_w: int, canvas_h: int,
                 layer_order: list, layer_frames: dict,
                 frame_count: int, fps: int, path: str,
                 frame_offset: int = 1):
        super().__init__()
        self._atlas_path   = atlas_path
        self._sprites      = sprites
        self._canvas_w     = canvas_w
        self._canvas_h     = canvas_h
        self._layer_order  = layer_order
        self._layer_frames = layer_frames
        self._frame_count  = frame_count
        self._fps          = max(1, fps)
        self._path         = path
        self._frame_offset = frame_offset

    def run(self):
        try:
            atlas    = QImage(str(self._atlas_path))
            duration = max(20, round(1000 / self._fps))
            pil_frames = []
            for i in range(self._frame_count):
                pix = composite_sheet_frame(
                    atlas, self._sprites, self._canvas_w, self._canvas_h,
                    self._layer_order, self._layer_frames, i,
                    self._frame_offset,
                )
                if pix and not pix.isNull():
                    arr = _qimage_to_rgba(pix.toImage())
                    pil_frames.append(PILImage.fromarray(arr).convert("RGBA"))
            if pil_frames:
                # Convert to P-mode with transparency for GIF
                converted = []
                for img in pil_frames:
                    bg = PILImage.new("RGBA", img.size, (0, 0, 0, 0))
                    p_img = PILImage.alpha_composite(bg, img).quantize(
                        colors=255, method=PILImage.Quantize.FASTOCTREE, dither=0
                    )
                    p_img.info["transparency"] = 0
                    converted.append(p_img)
                converted[0].save(
                    self._path, format="GIF",
                    save_all=True, append_images=converted[1:],
                    duration=duration, loop=0, disposal=2,
                )
                self.done.emit(self._path)
            else:
                self.done.emit("")
        except Exception:
            self.done.emit("")


class SheetPsdSaveWorker(QThread):
    done = pyqtSignal(str)  # path on success, "" on error

    def __init__(self, atlas_path: Path, sprites: dict,
                 canvas_w: int, canvas_h: int,
                 layer_order: list, layer_frames: dict,
                 frame_count: int, path: str,
                 frame_offset: int = 1):
        super().__init__()
        self._atlas_path   = atlas_path
        self._sprites      = sprites
        self._canvas_w     = canvas_w
        self._canvas_h     = canvas_h
        self._layer_order  = layer_order
        self._layer_frames = layer_frames
        self._frame_count  = frame_count
        self._path         = path
        self._frame_offset = frame_offset

    def run(self):
        try:
            groups = []
            for i in range(self._frame_count):
                ldata = extract_sheet_frame_layers(
                    self._atlas_path, self._sprites,
                    self._canvas_w, self._canvas_h,
                    self._layer_order, self._layer_frames, i,
                    self._frame_offset,
                )
                if ldata:
                    groups.append((f"Frame {i + 1:03d}", ldata))
            if groups:
                write_layered_psd(groups, self._canvas_w, self._canvas_h, self._path)
                self.done.emit(self._path)
            else:
                self.done.emit("")
        except Exception:
            self.done.emit("")


class SceneExportWorker(QThread):
    progress = pyqtSignal(int, int)
    done = pyqtSignal(str, str)

    def __init__(self, ccbi_path: Path, bg_dir: Path, tex_dir: Path, seq_id: int, fmt: str, target: Path, fps: int = 24):
        super().__init__()
        self._ccbi_path = ccbi_path
        self._bg_dir = bg_dir
        self._tex_dir = tex_dir
        self._seq_id = seq_id
        self._fmt = fmt
        self._target = target
        self._fps = max(1, fps)

    def run(self):
        try:
            scene = setup_scene(self._ccbi_path, self._bg_dir, self._tex_dir)
            if self._seq_id is not None:
                scene["seq_id"] = self._seq_id
                for seq in scene.get("sequences", []):
                    if seq.get("id") == self._seq_id:
                        scene["duration"] = max(0.001, float(seq.get("duration") or 1.0))
                        break

            full_w = max(1, scene.get("canvas_w", CANVAS_W))
            full_h = max(1, scene.get("canvas_h", CANVAS_H))
            scale = min(1.0, 1280 / full_w, 720 / full_h)
            scene["render_scale"] = scale
            out_w = max(1, int(full_w * scale))
            out_h = max(1, int(full_h * scale))
            duration_s = max(0.001, float(scene.get("duration") or 1.0))
            frame_count = max(1, min(600, int(round(duration_s * self._fps))))
            dt = duration_s / frame_count
            texcache = TextureCache(self._tex_dir)

            frames = []
            groups = []
            self._target.parent.mkdir(parents=True, exist_ok=True)
            if self._fmt == "PNG":
                self._target.mkdir(parents=True, exist_ok=True)

            for i in range(frame_count):
                scene["time"] = i * dt
                for em in scene.get("emitters", []):
                    em.update(dt if i else 0.0)
                canvas = QImage(out_w, out_h, QImage.Format.Format_ARGB32)
                render_scene_to_image(canvas, scene, texcache)

                if self._fmt == "PNG":
                    canvas.save(str(self._target / f"frame_{i + 1:04d}.png"), "PNG")
                elif self._fmt == "GIF":
                    frames.append(PILImage.fromarray(_qimage_to_rgba(canvas)).convert("RGBA"))
                else:
                    groups.append((f"Frame {i + 1:04d}", [(f"Frame {i + 1:04d}", canvas.copy(), 0, 0)]))

                self.progress.emit(i + 1, frame_count)

            if self._fmt == "GIF":
                if not frames:
                    self.done.emit("", "No frames were rendered.")
                    return
                duration_ms = max(20, round(1000 / self._fps))
                converted = []
                for img in frames:
                    p_img = img.quantize(colors=255, method=PILImage.Quantize.FASTOCTREE, dither=0)
                    p_img.info["transparency"] = 0
                    converted.append(p_img)
                converted[0].save(
                    str(self._target), format="GIF", save_all=True,
                    append_images=converted[1:], duration=duration_ms,
                    loop=0, disposal=2,
                )
            elif self._fmt == "PSD":
                if not groups:
                    self.done.emit("", "No frames were rendered.")
                    return
                write_layered_psd(groups, out_w, out_h, str(self._target))

            self.done.emit(str(self._target), "")
        except Exception as exc:
            self.done.emit("", str(exc))
