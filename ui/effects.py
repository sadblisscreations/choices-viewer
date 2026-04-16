import re
from pathlib import Path

from PIL import Image as PILImage
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSizePolicy, QSlider, QSplitter, QVBoxLayout, QWidget,
)

from ..parsers.plist_parser import parse_plist
from ..compositing import analyze_spritesheet, composite_sheet_frame
from ..psd import _qimage_to_rgba, extract_sheet_frame_layers, write_layered_psd
from ..workers import GifSaveWorker, SheetPsdSaveWorker
from .style import TEXT
from .custom import PreviewLabel
from . import separator


class EffectsTab(QWidget):
    def __init__(self, assets: Path, sheets: list):
        super().__init__()
        self._assets       = assets
        self._sheets       = sheets         # [(name, plist, png)]
        self._sprites      = {}
        self._atlas_path   = None
        self._canvas_w     = 0
        self._canvas_h     = 0
        self._layer_order  = []
        self._layer_frames = {}
        self._frame_count  = 1
        self._frame_idx    = 0
        self._frame_offset = 1
        self._playing      = False
        self._save_worker  = None

        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._next_frame)

        self._build_ui()
        if sheets:
            self._list.setCurrentRow(0)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(180)
        left.setMaximumWidth(340)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 8, 8)
        lv.setSpacing(6)

        hdr = QLabel("SPRITESHEETS")
        hdr.setStyleSheet("font-size: 10px; font-weight: bold; color: " + TEXT + "; letter-spacing: 1px;")
        lv.addWidget(hdr)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.textChanged.connect(self._filter_list)
        lv.addWidget(self._search)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        for name, plist, png in self._sheets:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, (plist, png))
            self._list.addItem(item)
        self._list.currentItemChanged.connect(self._on_select)
        lv.addWidget(self._list, stretch=1)

        self._count_lbl = QLabel(f"{len(self._sheets)} effects")
        self._count_lbl.setStyleSheet("font-size: 10px; color: " + TEXT + "; background: transparent;")
        lv.addWidget(self._count_lbl)

        # ── Right panel ───────────────────────────────────────────────────────
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 12, 12, 12)
        rv.setSpacing(8)

        self._title_lbl = QLabel("Spritesheets Viewer")
        self._title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: " + TEXT + "; background: transparent;")
        rv.addWidget(self._title_lbl)

        self._preview = PreviewLabel()
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        rv.addWidget(self._preview, stretch=1)

        self._info_lbl = QLabel("Select an effect")
        self._info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_lbl.setStyleSheet("font-size: 11px; color: #808080; background: transparent;")
        rv.addWidget(self._info_lbl)

        # Playback controls
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(4)

        self._first_btn = QPushButton("|<")
        self._prev_btn  = QPushButton("<")
        self._play_btn  = QPushButton("Play")
        self._next_btn  = QPushButton(">")
        self._last_btn  = QPushButton(">|")
        for btn in (self._first_btn, self._prev_btn, self._play_btn,
                    self._next_btn, self._last_btn):
            btn.setFixedHeight(26)
            btn.setEnabled(False)
        self._play_btn.setObjectName("primary")
        self._play_btn.setFixedWidth(70)

        self._first_btn.clicked.connect(self._go_first)
        self._prev_btn.clicked.connect(self._go_prev)
        self._play_btn.clicked.connect(self._toggle_play)
        self._next_btn.clicked.connect(self._go_next)
        self._last_btn.clicked.connect(self._go_last)

        fps_lbl = QLabel("FPS:")
        fps_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; background: transparent;")
        self._fps_combo = QComboBox()
        self._fps_combo.addItems(["6", "8", "10", "12", "15", "18", "24"])
        self._fps_combo.setCurrentIndex(3)   # 12 fps default
        self._fps_combo.setFixedWidth(60)
        self._fps_combo.currentIndexChanged.connect(self._on_fps_changed)

        ctrl_row.addWidget(self._first_btn)
        ctrl_row.addWidget(self._prev_btn)
        ctrl_row.addWidget(self._play_btn)
        ctrl_row.addWidget(self._next_btn)
        ctrl_row.addWidget(self._last_btn)
        ctrl_row.addStretch()
        ctrl_row.addWidget(fps_lbl)
        ctrl_row.addWidget(self._fps_combo)
        rv.addLayout(ctrl_row)

        # Frame slider
        slider_row = QHBoxLayout()
        slider_row.setSpacing(6)
        frame_lbl = QLabel("Frame:")
        frame_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; background: transparent;")
        self._frame_slider = QSlider(Qt.Orientation.Horizontal)
        self._frame_slider.setMinimum(0)
        self._frame_slider.setMaximum(0)
        self._frame_slider.setEnabled(False)
        self._frame_slider.valueChanged.connect(self._on_slider_changed)
        self._frame_num_lbl = QLabel("0 / 0")
        self._frame_num_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; background: transparent;")
        self._frame_num_lbl.setFixedWidth(60)
        slider_row.addWidget(frame_lbl)
        slider_row.addWidget(self._frame_slider, stretch=1)
        slider_row.addWidget(self._frame_num_lbl)
        rv.addLayout(slider_row)

        rv.addWidget(separator())

        # Save bar
        save_row = QHBoxLayout()
        save_row.setSpacing(6)
        fmt_lbl = QLabel("Format:")
        fmt_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; background: transparent;")
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["GIF", "PNG", "PSD"])
        self._fmt_combo.setFixedWidth(80)
        self._save_frame_btn = QPushButton("Save Frame…")
        self._save_frame_btn.setEnabled(False)
        self._save_anim_btn  = QPushButton("Save All Frames…")
        self._save_anim_btn.setEnabled(False)
        self._save_frame_btn.clicked.connect(self._save_frame)
        self._save_anim_btn.clicked.connect(self._save_all_frames)
        save_row.addWidget(fmt_lbl)
        save_row.addWidget(self._fmt_combo)
        save_row.addWidget(self._save_frame_btn)
        save_row.addWidget(self._save_anim_btn)
        save_row.addStretch()
        rv.addLayout(save_row)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter)

    # ── List / filter ─────────────────────────────────────────────────────────

    def _filter_list(self, text: str):
        t = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(t) and t not in item.text().lower())

    # ── Selection ─────────────────────────────────────────────────────────────

    def _on_select(self, current, _prev=None):
        if current is None:
            return
        self._stop_playback()
        plist, png = current.data(Qt.ItemDataRole.UserRole)
        self._atlas_path = png
        sprites = parse_plist(plist)
        self._sprites = sprites
        # Derive CCBI path: assets/ccbi/{sheet_name}.ccbi lives two levels up
        # from assets/ccbi_spritesheets/large/{sheet_name}.plist.
        ccbi_path = plist.parent.parent.parent / "ccbi" / (plist.stem + ".ccbi")
        if not ccbi_path.exists():
            ccbi_path = None
        cw, ch, fc, lo, lf, fo = analyze_spritesheet(sprites, ccbi_path)
        self._canvas_w     = cw
        self._canvas_h     = ch
        self._frame_count  = fc
        self._layer_order  = lo
        self._layer_frames = lf
        self._frame_offset = fo
        self._frame_idx    = 0

        self._title_lbl.setText(current.text())

        self._frame_slider.blockSignals(True)
        self._frame_slider.setMaximum(max(0, fc - 1))
        self._frame_slider.setValue(0)
        self._frame_slider.setEnabled(fc > 1)
        self._frame_slider.blockSignals(False)

        has_anim = fc > 1
        for btn in (self._first_btn, self._prev_btn, self._next_btn, self._last_btn):
            btn.setEnabled(has_anim)
        self._play_btn.setEnabled(has_anim)
        self._save_frame_btn.setEnabled(True)
        self._save_anim_btn.setEnabled(True)

        self._render_current()

    def _render_current(self):
        atlas = QImage(str(self._atlas_path))
        pix   = composite_sheet_frame(
            atlas, self._sprites, self._canvas_w, self._canvas_h,
            self._layer_order, self._layer_frames, self._frame_idx,
            self._frame_offset,
        )
        self._preview.setSourcePixmap(pix)
        self._frame_num_lbl.setText(f"{self._frame_idx + 1} / {self._frame_count}")
        self._frame_slider.blockSignals(True)
        self._frame_slider.setValue(self._frame_idx)
        self._frame_slider.blockSignals(False)
        self._info_lbl.setText(
            f"{self._canvas_w} × {self._canvas_h} px  •  "
            f"{self._frame_count} frame{'s' if self._frame_count != 1 else ''}  •  "
            f"{len(self._layer_order)} layer{'s' if len(self._layer_order) != 1 else ''}"
        )

    # ── Playback ──────────────────────────────────────────────────────────────

    def _fps(self) -> int:
        return int(self._fps_combo.currentText())

    def _toggle_play(self):
        if self._playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        if self._frame_count <= 1:
            return
        self._playing = True
        self._play_btn.setText("Pause")
        self._anim_timer.start(max(20, round(1000 / self._fps())))

    def _stop_playback(self):
        self._playing = False
        self._play_btn.setText("Play")
        self._anim_timer.stop()

    def _next_frame(self):
        self._frame_idx = (self._frame_idx + 1) % self._frame_count
        self._render_current()

    def _go_first(self):
        self._stop_playback()
        self._frame_idx = 0
        self._render_current()

    def _go_prev(self):
        self._stop_playback()
        self._frame_idx = (self._frame_idx - 1) % self._frame_count
        self._render_current()

    def _go_next(self):
        self._stop_playback()
        self._next_frame()

    def _go_last(self):
        self._stop_playback()
        self._frame_idx = self._frame_count - 1
        self._render_current()

    def _on_slider_changed(self, value: int):
        if self._playing:
            self._stop_playback()
        self._frame_idx = value
        self._render_current()

    def _on_fps_changed(self):
        if self._playing:
            self._anim_timer.setInterval(max(20, round(1000 / self._fps())))

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save_frame(self):
        if not self._sprites:
            return
        fmt  = self._fmt_combo.currentText()
        safe = re.sub(r'[<>:"/\\|?*]', "_", self._title_lbl.text())
        frame_label = f"frame_{self._frame_idx + 1:03d}"

        if fmt == "PNG":
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Frame as PNG",
                str(Path.home() / f"{safe}_{frame_label}.png"),
                "PNG Image (*.png)",
            )
            if not path:
                return
            atlas = QImage(str(self._atlas_path))
            pix = composite_sheet_frame(
                atlas, self._sprites, self._canvas_w, self._canvas_h,
                self._layer_order, self._layer_frames, self._frame_idx,
                self._frame_offset,
            )
            if pix and not pix.isNull():
                pix.save(path, "PNG")
                QMessageBox.information(self, "Saved", f"Saved frame to:\n{path}")

        elif fmt == "GIF":
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Frame as GIF",
                str(Path.home() / f"{safe}_{frame_label}.gif"),
                "GIF Image (*.gif)",
            )
            if not path:
                return
            atlas = QImage(str(self._atlas_path))
            pix = composite_sheet_frame(
                atlas, self._sprites, self._canvas_w, self._canvas_h,
                self._layer_order, self._layer_frames, self._frame_idx,
                self._frame_offset,
            )
            if pix and not pix.isNull():
                arr = _qimage_to_rgba(pix.toImage())
                img = PILImage.fromarray(arr).convert("RGBA")
                img.save(path, format="GIF")
                QMessageBox.information(self, "Saved", f"Saved frame to:\n{path}")

        elif fmt == "PSD":
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Frame as PSD",
                str(Path.home() / f"{safe}_{frame_label}.psd"),
                "Photoshop PSD (*.psd)",
            )
            if not path:
                return
            ldata = extract_sheet_frame_layers(
                self._atlas_path, self._sprites,
                self._canvas_w, self._canvas_h,
                self._layer_order, self._layer_frames, self._frame_idx,
                self._frame_offset,
            )
            if ldata:
                write_layered_psd([("", ldata)], self._canvas_w, self._canvas_h, path)
                QMessageBox.information(self, "Saved", f"Saved layered PSD to:\n{path}")

    def _save_all_frames(self):
        if not self._sprites:
            return
        fmt  = self._fmt_combo.currentText()
        safe = re.sub(r'[<>:"/\\|?*]', "_", self._title_lbl.text())

        if fmt == "PNG":
            folder = QFileDialog.getExistingDirectory(
                self, "Save All Frames as PNG — Choose Folder", str(Path.home())
            )
            if not folder:
                return
            self._disable_save()
            atlas = QImage(str(self._atlas_path))
            saved = 0
            for i in range(self._frame_count):
                pix = composite_sheet_frame(
                    atlas, self._sprites, self._canvas_w, self._canvas_h,
                    self._layer_order, self._layer_frames, i,
                    self._frame_offset,
                )
                if pix and not pix.isNull():
                    pix.save(str(Path(folder) / f"{safe}_frame_{i+1:03d}.png"), "PNG")
                    saved += 1
            self._enable_save()
            QMessageBox.information(self, "Saved", f"Saved {saved} PNG frames to:\n{folder}")

        elif fmt == "GIF":
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Animated GIF",
                str(Path.home() / f"{safe}.gif"),
                "Animated GIF (*.gif)",
            )
            if not path:
                return
            self._disable_save()
            self._info_lbl.setText("Building GIF…")
            self._save_worker = GifSaveWorker(
                self._atlas_path, self._sprites,
                self._canvas_w, self._canvas_h,
                self._layer_order, self._layer_frames,
                self._frame_count, self._fps(), path,
                self._frame_offset,
            )
            self._save_worker.done.connect(self._on_gif_done)
            self._save_worker.start()

        elif fmt == "PSD":
            path, _ = QFileDialog.getSaveFileName(
                self, "Save All Frames as Layered PSD",
                str(Path.home() / f"{safe}.psd"),
                "Photoshop PSD (*.psd)",
            )
            if not path:
                return
            self._disable_save()
            self._info_lbl.setText("Building PSD…")
            self._save_worker = SheetPsdSaveWorker(
                self._atlas_path, self._sprites,
                self._canvas_w, self._canvas_h,
                self._layer_order, self._layer_frames,
                self._frame_count, path,
                self._frame_offset,
            )
            self._save_worker.done.connect(self._on_psd_done)
            self._save_worker.start()

    def _on_gif_done(self, path: str):
        self._enable_save()
        self._render_current()
        if path:
            QMessageBox.information(self, "Saved", f"Saved animated GIF to:\n{path}")
        else:
            QMessageBox.warning(self, "Error", "Failed to save GIF.")

    def _on_psd_done(self, path: str):
        self._enable_save()
        self._render_current()
        if path:
            QMessageBox.information(self, "Saved", f"Saved layered PSD to:\n{path}")
        else:
            QMessageBox.warning(self, "Error", "Failed to save PSD.")

    def _disable_save(self):
        self._save_frame_btn.setEnabled(False)
        self._save_anim_btn.setEnabled(False)

    def _enable_save(self):
        self._save_frame_btn.setEnabled(True)
        self._save_anim_btn.setEnabled(True)

    def update_assets(self, assets: Path, sheets: list):
        self._stop_playback()
        self._assets = assets
        self._sheets = sheets
        self._list.clear()
        for name, plist, png in sheets:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, (plist, png))
            self._list.addItem(item)
        self._count_lbl.setText(f"{len(sheets)} effects")
        if self._list.count():
            self._list.setCurrentRow(0)
