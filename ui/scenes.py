import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from ..ccbi import CANVAS_W, CANVAS_H, setup_scene, render_scene_to_image, TextureCache
from ..style import TEXT
from . import separator

CANVAS_BG = QColor(15, 15, 26)


class ScenePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = None
        self._texcache = None
        self._canvas = QImage(CANVAS_W, CANVAS_H, QImage.Format.Format_ARGB32)
        self._canvas.fill(CANVAS_BG)
        self._last_time = time.perf_counter()
        self._particle_count = 0
        self.setMinimumSize(320, 260)
        self.setStyleSheet("background: #0f0f1a;")

    def set_scene(self, ccbi_path: Path, bg_dir: Path, tex_dir: Path):
        self._scene = setup_scene(ccbi_path, bg_dir, tex_dir)
        self._texcache = TextureCache(tex_dir)
        self._last_time = time.perf_counter()
        self.update()

    def restart(self):
        if self._scene:
            ccbi_path = self._scene["_ccbi_path"]
            bg_dir = self._scene["_bg_dir"]
            tex_dir = self._scene["_tex_dir"]
            self.set_scene(ccbi_path, bg_dir, tex_dir)

    def start_animation(self):
        self._last_time = time.perf_counter()

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

    def tick(self):
        if not self._scene:
            return
        now = time.perf_counter()
        dt = min(now - self._last_time, 0.05)
        self._last_time = now
        for em in self._scene["emitters"]:
            em.update(dt)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._scene and self._texcache:
            self._particle_count = render_scene_to_image(self._canvas, self._scene, self._texcache)

        src = QRect(0, 0, CANVAS_W, CANVAS_H)
        scale_w = self.width()
        scale_h = int(self.width() * CANVAS_H / CANVAS_W)
        if scale_h > self.height():
            scale_h = self.height()
            scale_w = int(self.height() * CANVAS_W / CANVAS_H)
        x = (self.width() - scale_w) // 2
        y = (self.height() - scale_h) // 2
        dst = QRect(x, y, scale_w, scale_h)
        painter.fillRect(self.rect(), CANVAS_BG)
        painter.drawImage(dst, self._canvas, src)
        painter.end()


class ScenesTab(QWidget):
    def __init__(self, assets: Path, scenes: list):
        super().__init__()
        self._assets = assets
        self._scenes = scenes

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(16)

        self._build_ui()
        if scenes:
            self._list.setCurrentRow(0)

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

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.textChanged.connect(self._filter_list)
        lv.addWidget(self._search)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        for name, ccbi in self._scenes:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, ccbi)
            self._list.addItem(item)
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
        for btn in (self._prev_btn, self._next_btn, self._restart_btn):
            btn.setFixedHeight(26)

        self._prev_btn.clicked.connect(self._prev_scene)
        self._next_btn.clicked.connect(self._next_scene)
        self._restart_btn.clicked.connect(self._restart)

        ctrl_row.addWidget(self._prev_btn)
        ctrl_row.addWidget(self._next_btn)
        ctrl_row.addWidget(self._restart_btn)
        ctrl_row.addStretch()
        rv.addLayout(ctrl_row)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter)

    def _filter_list(self, text: str):
        t = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(t) and t not in item.text().lower())

    def _on_select(self, current, _prev=None):
        if current is None:
            return
        ccbi_path = current.data(Qt.ItemDataRole.UserRole)
        self._title_lbl.setText(current.text())
        bg_dir = self._assets / "backgrounds" / "large"
        tex_dir = self._assets / "ccbi_images" / "2x"
        try:
            self._preview.set_scene(ccbi_path, bg_dir, tex_dir)
            self._preview.start_animation()
        except Exception as e:
            QMessageBox.warning(self, "Error Loading Scene", f"Failed to parse CCBI file:\n{ccbi_path.name}\n\n{e}")
            self._preview._scene = None
            self._preview.update()

    def _prev_scene(self):
        row = self._list.currentRow()
        if row > 0:
            self._list.setCurrentRow(row - 1)

    def _next_scene(self):
        row = self._list.currentRow()
        if row < self._list.count() - 1:
            self._list.setCurrentRow(row + 1)

    def _restart(self):
        self._preview.restart()

    def _on_tick(self):
        self._preview.tick()
        if self._preview._scene:
            active = self._preview.active_emitters()
            total = self._preview.total_emitters()
            parts = self._preview.particle_count()
            seqs = ", ".join(self._preview.scene_seqs()[:3]) or "none"
            self._info_lbl.setText(
                f"Emitters: {total} (active {active})  •  Particles: {parts}  •  Seqs: {seqs}"
            )

    def update_assets(self, assets: Path, scenes: list):
        self._assets = assets
        self._scenes = scenes
        self._list.clear()
        for name, ccbi in scenes:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, ccbi)
            self._list.addItem(item)
        self._count_lbl.setText(f"{len(scenes)} scenes")
        if self._list.count():
            self._list.setCurrentRow(0)
        else:
            self._preview._scene = None
            self._preview.update()
