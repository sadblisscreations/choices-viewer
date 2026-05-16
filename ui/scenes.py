import re
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton,
    QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from ..parsers.ccbi_parser import CANVAS_W, CANVAS_H, render_scene_to_image, TextureCache
from ..workers import SceneExportWorker, SceneLoadWorker
from .style import TEXT
from . import separator
from .characters import HighlightingComboBox

CANVAS_BG = QColor(15, 15, 26)
MAX_PREVIEW_W = 960
MAX_PREVIEW_H = 540


class ScenePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = None
        self._texcache = None
        self._canvas = QImage(CANVAS_W, CANVAS_H, QImage.Format.Format_ARGB32)
        self._canvas.fill(CANVAS_BG)
        self._last_time = time.perf_counter()
        self._last_update_time = 0.0
        self._last_render_ms = 0.0
        self._particle_count = 0
        self._dirty = True
        self._transparent_bg = False
        self.setMinimumSize(320, 260)
        self.setStyleSheet("background: #0f0f1a;")

    def set_scene(self, ccbi_path: Path, bg_dir: Path, tex_dir: Path):
        from ..parsers.ccbi_parser import setup_scene
        self.set_prepared_scene(setup_scene(ccbi_path, bg_dir, tex_dir), tex_dir)

    def set_prepared_scene(self, scene: dict, tex_dir: Path):
        self._scene = scene
        self._texcache = TextureCache(tex_dir)
        full_w = max(1, self._scene.get("canvas_w", CANVAS_W))
        full_h = max(1, self._scene.get("canvas_h", CANVAS_H))
        scale = min(1.0, MAX_PREVIEW_W / full_w, MAX_PREVIEW_H / full_h)
        self._scene["render_scale"] = scale
        self._canvas = QImage(
            max(1, int(full_w * scale)),
            max(1, int(full_h * scale)),
            QImage.Format.Format_ARGB32,
        )
        self._canvas.fill(CANVAS_BG)
        self._last_time = time.perf_counter()
        self._last_update_time = 0.0
        self._last_render_ms = 0.0
        self._dirty = True
        self.update()

    def restart(self):
        if self._scene:
            ccbi_path = self._scene["_ccbi_path"]
            bg_dir = self._scene["_bg_dir"]
            tex_dir = self._scene["_tex_dir"]
            self.set_scene(ccbi_path, bg_dir, tex_dir)

    def start_animation(self):
        self._last_time = time.perf_counter()
        self._last_update_time = 0.0

    def render_ms(self) -> float:
        return self._last_render_ms

    def set_transparent_background(self, enabled: bool):
        self._transparent_bg = enabled

    def particle_count(self) -> int:
        return self._particle_count

    def active_emitters(self) -> int:
        if not self._scene:
            return 0
        return sum(1 for e in self._scene["emitters"] if e.active)

    def total_emitters(self) -> int:
        return len(self._scene["emitters"]) if self._scene else 0

    def scene_seqs(self) -> list:
        return self._scene.get("seqs", []) if self._scene else []

    def sequences(self) -> list:
        return self._scene.get("sequences", []) if self._scene else []

    def current_sequence_id(self) -> int:
        return self._scene.get("seq_id", 0) if self._scene else 0

    def set_sequence(self, seq_id: int):
        if not self._scene:
            return
        self._scene["seq_id"] = seq_id
        self._scene["duration"] = 1.0
        for seq in self._scene.get("sequences", []):
            if seq.get("id") == seq_id:
                self._scene["duration"] = max(0.001, float(seq.get("duration") or 1.0))
                break
        self._scene["time"] = 0.0
        self._last_time = time.perf_counter()
        self._dirty = True
        self.update()

    def _needs_tick(self) -> bool:
        if not self._scene:
            return False
        seq_id = self._scene.get("seq_id", 0)
        if seq_id in self._scene.get("animated_seq_ids", set()):
            return True
        return any(e.active or e.particles for e in self._scene.get("emitters", []))

    def tick(self):
        if not self._scene:
            return
        now = time.perf_counter()
        dt = min(now - self._last_time, 0.05)
        self._last_time = now
        if not self._needs_tick():
            return
        self._scene["time"] = (self._scene.get("time", 0.0) + dt) % max(0.001, self._scene.get("duration", 1.0))
        for em in self._scene["emitters"]:
            em.update(dt)

        if self._last_render_ms > 45:
            frame_interval = 1 / 15
        elif self._last_render_ms > 28:
            frame_interval = 1 / 20
        else:
            frame_interval = 1 / 30
        if now - self._last_update_time < frame_interval:
            return

        self._last_update_time = now
        self._dirty = True
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._scene and self._texcache and self._dirty:
            start = time.perf_counter()
            self._particle_count = render_scene_to_image(self._canvas, self._scene, self._texcache)
            self._last_render_ms = (time.perf_counter() - start) * 1000
            self._dirty = False

        src = QRect(0, 0, self._canvas.width(), self._canvas.height())
        scale_w = self.width()
        scale_h = int(self.width() * self._canvas.height() / max(1, self._canvas.width()))
        if scale_h > self.height():
            scale_h = self.height()
            scale_w = int(self.height() * self._canvas.width() / max(1, self._canvas.height()))
        x = (self.width() - scale_w) // 2
        y = (self.height() - scale_h) // 2
        dst = QRect(x, y, scale_w, scale_h)
        painter.fillRect(self.rect(), CANVAS_BG)
        painter.drawImage(dst, self._canvas, src)
        painter.end()


class ScenesTab(QWidget):
    def __init__(self, assets: Path, scenes: list, scene_books: dict | None = None):
        super().__init__()
        self._assets = assets
        self._scenes = scenes
        self._scene_books = scene_books or {}
        self._scene_book_index = {}
        self._scene_books_cache = {}
        self._rebuild_scene_book_index()
        self._export_worker = None
        self._scene_load_workers = []
        self._scene_load_request = 0
        self._pending_scene_load = None
        self._last_info_update = 0.0

        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.timeout.connect(self._load_pending_scene)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(33)

        self._build_ui()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left sidebar
        left = QWidget()
        left.setMinimumWidth(180)
        left.setMaximumWidth(340)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 8, 8)
        lv.setSpacing(6)

        hdr = QLabel("SCENES")
        hdr.setStyleSheet("font-size: 10px; font-weight: bold; color: " + TEXT + "; letter-spacing: 1px;")
        lv.addWidget(hdr)

        self._book_combo = HighlightingComboBox()
        self._book_combo.setMaxVisibleItems(20)
        self._book_combo.currentIndexChanged.connect(self._filter_list)
        lv.addWidget(self._book_combo)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.textChanged.connect(self._filter_list)
        lv.addWidget(self._search)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        self._list.currentItemChanged.connect(self._on_select)
        lv.addWidget(self._list, stretch=1)

        self._count_lbl = QLabel(f"{len(self._scenes)} scenes")
        self._count_lbl.setStyleSheet("font-size: 10px; color: " + TEXT + "; background: transparent;")
        lv.addWidget(self._count_lbl)

        # Right panel
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 12, 12, 12)
        rv.setSpacing(8)

        self._title_lbl = QLabel("Scene Viewer")
        self._title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: " + TEXT + "; background: transparent;")
        rv.addWidget(self._title_lbl)

        self._preview = ScenePreview()
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        rv.addWidget(self._preview, stretch=1)

        self._info_lbl = QLabel("Select a scene")
        self._info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_lbl.setStyleSheet("font-size: 11px; color: #808080; background: transparent;")
        rv.addWidget(self._info_lbl)

        # Controls
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(4)

        self._prev_btn = QPushButton("<")
        self._next_btn = QPushButton(">")
        self._restart_btn = QPushButton("Restart")
        self._export_btn = QPushButton("Save Scene...")
        for btn in (self._prev_btn, self._next_btn, self._restart_btn, self._export_btn):
            btn.setFixedHeight(26)

        self._prev_btn.clicked.connect(self._prev_scene)
        self._next_btn.clicked.connect(self._next_scene)
        self._restart_btn.clicked.connect(self._restart)
        self._export_btn.clicked.connect(self._export_scene)
        self._export_btn.setEnabled(False)

        ctrl_row.addWidget(self._prev_btn)
        ctrl_row.addWidget(self._next_btn)
        ctrl_row.addWidget(self._restart_btn)
        self._seq_combo = QComboBox()
        self._seq_combo.setMinimumWidth(280)
        self._seq_combo.currentIndexChanged.connect(self._on_sequence_changed)
        ctrl_row.addWidget(self._seq_combo, stretch=1)
        self._transparent_chk = QCheckBox("Transparent background")
        self._transparent_chk.toggled.connect(self._on_transparency_changed)
        ctrl_row.addWidget(self._transparent_chk)
        self._export_combo = QComboBox()
        self._export_combo.addItems(["PNG Sequence", "GIF", "PSD"])
        ctrl_row.addWidget(self._export_combo)
        ctrl_row.addWidget(self._export_btn)
        ctrl_row.addStretch()
        rv.addLayout(ctrl_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        rv.addWidget(self._progress)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter)

        self._rebuild_book_combo()
        self._filter_list()

    @staticmethod
    def _book_display(book: str) -> str:
        return book.removeprefix("book_").replace("_", " ").strip().title()

    def _scene_keys_for(self, ccbi: Path) -> set:
        keys = {ccbi.stem.split("-v")[0]}
        try:
            rel_key = str(ccbi.relative_to(self._assets).with_suffix("")).replace("\\", "/")
            keys.add(rel_key.split("-v")[0])
        except ValueError:
            pass
        return keys

    def _rebuild_scene_book_index(self):
        self._scene_book_index = {}
        self._scene_books_cache = {}
        for book, keys in self._scene_books.items():
            for key in keys:
                self._scene_book_index.setdefault(key, set()).add(book)

    def _books_for(self, ccbi: Path) -> set:
        cache_key = str(ccbi)
        cached = self._scene_books_cache.get(cache_key)
        if cached is not None:
            return cached
        keys = self._scene_keys_for(ccbi)
        books = set()
        for key in keys:
            books.update(self._scene_book_index.get(key, ()))
        self._scene_books_cache[cache_key] = books
        return books

    def _rebuild_book_combo(self):
        per_book_count: dict = {}
        unassigned = 0
        for _name, ccbi in self._scenes:
            books = self._books_for(ccbi)
            if not books:
                unassigned += 1
                continue
            for book in books:
                per_book_count[book] = per_book_count.get(book, 0) + 1

        self._book_combo.blockSignals(True)
        self._book_combo.clear()
        self._book_combo.addItem(f"All Books ({len(self._scenes)})", "")
        for book in sorted(per_book_count.keys()):
            self._book_combo.addItem(f"{self._book_display(book)} ({per_book_count[book]})", book)
        if unassigned:
            self._book_combo.addItem(f"— Unassigned ({unassigned})", "__unassigned__")
        self._book_combo.blockSignals(False)

    def _sort_key(self, scene):
        name, ccbi = scene
        books = sorted(self._books_for(ccbi))
        if books:
            return (0, self._book_display(books[0]).lower(), name.lower())
        return (1, "zzzzzz", name.lower())

    def _filter_list(self, *_):
        book = self._book_combo.currentData() or ""
        t = self._search.text().lower()

        def book_ok(ccbi):
            books = self._books_for(ccbi)
            if not book:
                return True
            if book == "__unassigned__":
                return not books
            return book in books

        filtered = [
            (name, ccbi) for name, ccbi in self._scenes
            if book_ok(ccbi) and (not t or t in name.lower())
        ]
        filtered.sort(key=self._sort_key)

        current = self._list.currentItem()
        current_path = current.data(Qt.ItemDataRole.UserRole) if current else None
        self._list.blockSignals(True)
        self._list.clear()
        restore_row = -1
        for name, ccbi in filtered:
            books = sorted(self._books_for(ccbi))
            label = name
            if not book and books:
                label = f"{self._book_display(books[0])} - {name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ccbi)
            item.setData(Qt.ItemDataRole.UserRole + 1, name)
            self._list.addItem(item)
            if current_path is not None and ccbi == current_path:
                restore_row = self._list.count() - 1
        n = len(filtered)
        self._count_lbl.setText(f"{n} scene{'s' if n != 1 else ''}")
        if restore_row >= 0:
            self._list.setCurrentRow(restore_row)
        self._list.blockSignals(False)
        if not self._list.count():
            self._preview._scene = None
            self._seq_combo.clear()
            self._export_btn.setEnabled(False)
            self._scene_load_request += 1
            self._hide_progress()
            self._preview.update()

    def _on_select(self, current, _prev=None):
        if current is None:
            return
        ccbi_path = current.data(Qt.ItemDataRole.UserRole)
        scene_name = current.data(Qt.ItemDataRole.UserRole + 1) or current.text()
        self._title_lbl.setText(scene_name)
        bg_dir = self._assets / "backgrounds" / "large"
        tex_dir = self._assets / "ccbi_images" / "2x"
        self._pending_scene_load = (ccbi_path, bg_dir, tex_dir)
        self._selection_timer.start(90)

    def _load_pending_scene(self):
        if self._pending_scene_load is None:
            return
        ccbi_path, bg_dir, tex_dir = self._pending_scene_load
        self._pending_scene_load = None
        self._start_scene_load(ccbi_path, bg_dir, tex_dir)

    def _start_scene_load(self, ccbi_path: Path, bg_dir: Path, tex_dir: Path):
        self._selection_timer.stop()
        self._scene_load_request += 1
        request_id = self._scene_load_request
        self._preview._scene = None
        self._seq_combo.clear()
        self._export_btn.setEnabled(False)
        self._info_lbl.setText("Loading scene...")
        self._show_busy_progress("Loading scene...")
        self._preview.update()

        worker = SceneLoadWorker(request_id, ccbi_path, bg_dir, tex_dir)
        self._scene_load_workers.append(worker)
        worker.done.connect(
            lambda rid, scene, error, td=tex_dir, cp=ccbi_path:
            self._on_scene_loaded(rid, scene, error, td, cp)
        )
        worker.finished.connect(lambda w=worker: self._cleanup_scene_loader(w))
        worker.start()

    def _cleanup_scene_loader(self, worker: SceneLoadWorker):
        if worker in self._scene_load_workers:
            self._scene_load_workers.remove(worker)

    def _on_scene_loaded(
        self,
        request_id: int,
        scene,
        error: str,
        tex_dir: Path,
        ccbi_path: Path,
    ):
        if request_id != self._scene_load_request:
            return
        if error or not scene:
            QMessageBox.warning(self, "Error Loading Scene", f"Failed to parse CCBI file:\n{ccbi_path.name}\n\n{error}")
            self._preview._scene = None
            self._seq_combo.clear()
            self._export_btn.setEnabled(False)
            self._hide_progress()
            self._preview.update()
            return

        self._preview.set_prepared_scene(scene, tex_dir)
        self._preview.set_transparent_background(self._transparent_chk.isChecked())
        self._populate_sequences()
        self._preview.start_animation()
        self._export_btn.setEnabled(True)
        self._hide_progress()

    def _prev_scene(self):
        row = self._list.currentRow()
        if row > 0:
            self._list.setCurrentRow(row - 1)

    def _next_scene(self):
        row = self._list.currentRow()
        if row < self._list.count() - 1:
            self._list.setCurrentRow(row + 1)

    def _restart(self):
        item = self._list.currentItem()
        if item is None:
            return
        ccbi_path = item.data(Qt.ItemDataRole.UserRole)
        self._start_scene_load(
            ccbi_path,
            self._assets / "backgrounds" / "large",
            self._assets / "ccbi_images" / "2x",
        )

    def _populate_sequences(self):
        self._seq_combo.blockSignals(True)
        self._seq_combo.clear()
        current_id = self._preview.current_sequence_id()
        current_index = 0
        for i, seq in enumerate(self._preview.sequences()):
            duration = float(seq.get("duration") or 0)
            label = f"{seq.get('name', 'Timeline')} ({duration:.2f}s)"
            self._seq_combo.addItem(label, int(seq.get("id", 0)))
            if int(seq.get("id", 0)) == current_id:
                current_index = i
        if self._seq_combo.count():
            self._seq_combo.setCurrentIndex(current_index)
        self._seq_combo.blockSignals(False)

    def _on_sequence_changed(self, index: int):
        if index < 0:
            return
        seq_id = self._seq_combo.itemData(index)
        if seq_id is not None:
            self._preview.set_sequence(int(seq_id))

    def _on_transparency_changed(self, enabled: bool):
        self._preview.set_transparent_background(enabled)

    def _show_busy_progress(self, text: str):
        self._progress.setRange(0, 0)
        self._progress.setValue(0)
        self._progress.setFormat(text)
        self._progress.setVisible(True)

    def _show_export_progress(self, done: int, total: int):
        self._progress.setRange(0, max(1, total))
        self._progress.setValue(done)
        self._progress.setFormat(f"Exporting scene: {done}/{total}")
        self._progress.setVisible(True)

    def _hide_progress(self):
        self._progress.setVisible(False)

    def _safe_scene_name(self) -> str:
        item = self._list.currentItem()
        name = item.data(Qt.ItemDataRole.UserRole + 1) if item else "scene"
        name = re.sub(r"\s+", "_", str(name).strip().lower())
        return re.sub(r'[<>:"/\\|?*]', "_", name) or "scene"

    def _export_scene(self):
        item = self._list.currentItem()
        if item is None or not self._preview._scene:
            return

        fmt_label = self._export_combo.currentText()
        safe = self._safe_scene_name()
        if fmt_label == "PNG Sequence":
            folder = QFileDialog.getExistingDirectory(
                self, "Save PNG Sequence", str(Path.home() / f"{safe}_frames")
            )
            if not folder:
                return
            target = Path(folder)
            fmt = "PNG"
        elif fmt_label == "GIF":
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Scene as GIF", str(Path.home() / f"{safe}.gif"), "GIF (*.gif)"
            )
            if not path:
                return
            target = Path(path)
            fmt = "GIF"
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Scene as Layered PSD", str(Path.home() / f"{safe}.psd"), "Photoshop PSD (*.psd)"
            )
            if not path:
                return
            target = Path(path)
            fmt = "PSD"

        ccbi_path = item.data(Qt.ItemDataRole.UserRole)
        bg_dir = self._assets / "backgrounds" / "large"
        tex_dir = self._assets / "ccbi_images" / "2x"
        self._export_btn.setEnabled(False)
        self._show_busy_progress("Preparing export...")
        self._export_worker = SceneExportWorker(
            ccbi_path,
            bg_dir,
            tex_dir,
            self._preview.current_sequence_id(),
            fmt,
            target,
            transparent_bg=self._transparent_chk.isChecked(),
        )
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.done.connect(self._on_export_done)
        self._export_worker.start()

    def _on_export_progress(self, done: int, total: int):
        self._show_export_progress(done, total)

    def _on_export_done(self, path: str, error: str):
        self._export_btn.setEnabled(self._preview._scene is not None)
        self._export_worker = None
        self._hide_progress()
        if path:
            QMessageBox.information(self, "Saved", f"Saved scene export to:\n{path}")
        else:
            QMessageBox.warning(self, "Error", f"Failed to export scene:\n{error or 'Unknown error'}")

    def _on_tick(self):
        self._preview.tick()
        if self._export_worker is not None:
            return
        if self._preview._scene:
            now = time.perf_counter()
            if now - self._last_info_update < 0.25:
                return
            self._last_info_update = now
            active = self._preview.active_emitters()
            total = self._preview.total_emitters()
            parts = self._preview.particle_count()
            seqs = ", ".join(self._preview.scene_seqs()[:3]) or "none"
            self._info_lbl.setText(
                f"Emitters: {total} (active {active})  •  Particles: {parts}  •  Seqs: {seqs}"
            )

    def update_assets(self, assets: Path, scenes: list, scene_books: dict | None = None):
        self._assets = assets
        self._scenes = scenes
        if scene_books is not None:
            self._scene_books = scene_books
        self._rebuild_scene_book_index()
        self._search.clear()
        self._rebuild_book_combo()
        self._filter_list()
