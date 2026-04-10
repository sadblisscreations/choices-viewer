from pathlib import Path

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from ..compositing import CUSTOM_LAYER_ORDER, CUSTOM_OPTIONAL, SLOT_LABELS, EMOTIONS
from ..psd import extract_custom_layers, write_layered_psd
from ..workers import CustomLoadWorker, SaveCustomEmotionsWorker
from ..style import ACCENT, BORDER, EMOTION_COLORS, PANEL_BG, SUBTLE, TEXT
from . import separator


class PreviewLabel(QLabel):
    """QLabel that scales a stored pixmap to fit, preserving aspect ratio."""

    def __init__(self):
        super().__init__()
        self._source = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 200)

    def setSourcePixmap(self, pix):
        self._source = pix
        self._rescale()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._source and not self._source.isNull():
            available = QSize(self.width() - 24, self.height() - 24)
            scaled = self._source.scaled(
                available,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            super().setPixmap(scaled)
        else:
            super().clear()


class CustomBuilderTab(QWidget):
    def __init__(self, assets: Path, custom_items: dict):
        super().__init__()
        self._items            = custom_items
        self._worker           = None
        self._save_worker      = None
        self._selected_emotion = "NEUTRAL"
        self._slot_combos: dict = {}
        self._emotion_btns: dict = {}

        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_refresh)

        self._build_ui()

        if custom_items:
            self._type_list.setCurrentRow(0)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(240)
        left.setMaximumWidth(420)
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(10, 10, 10, 10)
        left_vbox.setSpacing(8)

        type_hdr = QLabel("CHARACTER TYPE")
        type_hdr.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {SUBTLE}; letter-spacing: 1.5px;")
        left_vbox.addWidget(type_hdr)

        self._type_list = QListWidget()
        self._type_list.setMinimumHeight(80)
        self._type_list.setMaximumHeight(180)
        self._type_list.setUniformItemSizes(True)
        for ct in sorted(self._items.keys()):
            item = QListWidgetItem(self._fmt_type(ct))
            item.setData(Qt.ItemDataRole.UserRole, ct)
            self._type_list.addItem(item)
        self._type_list.currentItemChanged.connect(self._on_type_changed)
        left_vbox.addWidget(self._type_list)

        left_vbox.addWidget(separator())

        layers_hdr = QLabel("LAYERS")
        layers_hdr.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {SUBTLE}; letter-spacing: 1.5px;")
        left_vbox.addWidget(layers_hdr)

        # Scrollable slot area
        slot_scroll = QScrollArea()
        slot_scroll.setWidgetResizable(True)
        slot_scroll.setFrameShape(QFrame.Shape.NoFrame)

        slot_widget = QWidget()
        slot_vbox = QVBoxLayout(slot_widget)
        slot_vbox.setContentsMargins(0, 4, 4, 4)
        slot_vbox.setSpacing(10)

        ui_order = ["body", "face", "hair_b", "hair_f", "clothing", "hat_f", "prop_f", "prop_b", "acc", "tattoo"]
        for slot in ui_order:
            lbl_text = SLOT_LABELS.get(slot, slot.title())
            optional = slot in CUSTOM_OPTIONAL

            row = QWidget()
            rv = QVBoxLayout(row)
            rv.setContentsMargins(0, 0, 0, 0)
            rv.setSpacing(3)

            hdr_row = QHBoxLayout()
            hdr_row.setSpacing(6)
            slot_lbl = QLabel(lbl_text)
            slot_lbl.setStyleSheet(
                f"font-size: 11px; color: {'#9399b2' if not optional else SUBTLE};"
                f" font-weight: {'bold' if not optional else 'normal'};"
            )
            hdr_row.addWidget(slot_lbl)
            if optional:
                opt_tag = QLabel("optional")
                opt_tag.setStyleSheet(
                    f"font-size: 9px; color: {SUBTLE}; border: 1px solid {BORDER};"
                    f" border-radius: 2px; padding: 0 4px;"
                )
                hdr_row.addWidget(opt_tag)
            hdr_row.addStretch()
            rv.addLayout(hdr_row)

            combo = QComboBox()
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo.currentIndexChanged.connect(self._on_slot_changed)
            self._slot_combos[slot] = combo
            rv.addWidget(combo)

            # Emotion picker row (face slot only)
            if slot == "face":
                emo_row = QHBoxLayout()
                emo_row.setSpacing(3)
                emo_row.setContentsMargins(0, 2, 0, 0)
                btn_grp = QButtonGroup(self)
                btn_grp.setExclusive(True)
                for emo in EMOTIONS:
                    ec = EMOTION_COLORS.get(emo, ACCENT)
                    btn = QPushButton(emo.capitalize())
                    btn.setCheckable(True)
                    btn.setChecked(emo == "NEUTRAL")
                    btn.setFixedHeight(22)
                    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {PANEL_BG}; border: 1px solid {BORDER};
                            border-radius: 3px; font-size: 10px;
                            padding: 0 2px; color: {SUBTLE};
                        }}
                        QPushButton:checked {{
                            background: {ec}22; border-color: {ec};
                            color: {ec}; font-weight: bold;
                        }}
                        QPushButton:hover {{ color: {TEXT}; border-color: #585b70; }}
                    """)
                    btn.clicked.connect(lambda _checked, e=emo: self._set_emotion(e))
                    btn_grp.addButton(btn)
                    emo_row.addWidget(btn)
                    self._emotion_btns[emo] = btn
                rv.addLayout(emo_row)

            slot_vbox.addWidget(row)

        slot_vbox.addStretch()
        slot_scroll.setWidget(slot_widget)
        left_vbox.addWidget(slot_scroll, stretch=1)

        # ── Right preview ─────────────────────────────────────────────────────
        right = QWidget()
        rv2 = QVBoxLayout(right)
        rv2.setContentsMargins(20, 16, 20, 16)
        rv2.setSpacing(10)

        preview_hdr = QLabel("Custom Character")
        preview_hdr.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {TEXT};")
        rv2.addWidget(preview_hdr)

        self._preview = PreviewLabel()
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview.setStyleSheet(
            f"background: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 6px;"
        )
        rv2.addWidget(self._preview, stretch=1)

        self._status_lbl = QLabel("Select a character type to begin")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(f"font-size: 11px; color: {SUBTLE};")
        rv2.addWidget(self._status_lbl)

        # ── Save bar ──────────────────────────────────────────────────────────
        save_bar = QHBoxLayout()
        save_bar.setSpacing(8)

        custom_fmt_lbl = QLabel("Format:")
        custom_fmt_lbl.setStyleSheet(f"font-size: 11px; color: {SUBTLE};")
        self._custom_fmt_combo = QComboBox()
        self._custom_fmt_combo.addItems(["PNG", "JPEG", "PSD"])
        self._custom_fmt_combo.setFixedWidth(80)

        self._custom_save_btn = QPushButton("Save…")
        self._custom_save_btn.clicked.connect(self._save_preview)

        self._custom_save_all_btn = QPushButton("Save All Emotions…")
        self._custom_save_all_btn.clicked.connect(self._save_all_emotions)

        save_bar.addWidget(custom_fmt_lbl)
        save_bar.addWidget(self._custom_fmt_combo)
        save_bar.addStretch()
        save_bar.addWidget(self._custom_save_btn)
        save_bar.addWidget(self._custom_save_all_btn)
        rv2.addLayout(save_bar)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])
        outer.addWidget(splitter)

    # ── Data helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_type(ct: str) -> str:
        gmap = {"fem": "Female", "male": "Male", "masc": "Masc"}
        parts = ct.split("_", 1)
        gender = gmap.get(parts[0], parts[0].title())
        rest   = parts[1].replace("_", " ").title() if len(parts) > 1 else ""
        return f"{gender} {rest}".strip()

    def update_assets(self, assets: Path, custom_items: dict):
        self._items = custom_items
        self._type_list.blockSignals(True)
        self._type_list.clear()
        for ct in sorted(custom_items.keys()):
            item = QListWidgetItem(self._fmt_type(ct))
            item.setData(Qt.ItemDataRole.UserRole, ct)
            self._type_list.addItem(item)
        self._type_list.blockSignals(False)
        if self._type_list.count():
            self._type_list.setCurrentRow(0)

    # ── Slot population ───────────────────────────────────────────────────────

    def _on_type_changed(self, current, _prev=None):
        if current is None:
            return
        ct    = current.data(Qt.ItemDataRole.UserRole)
        slots = self._items.get(ct, {})

        for slot, combo in self._slot_combos.items():
            combo.blockSignals(True)
            combo.clear()
            items = slots.get(slot, [])
            if slot in CUSTOM_OPTIONAL:
                combo.addItem("— None —", None)
            if items:
                for label, plist, png in items:
                    combo.addItem(label, (plist, png))
                combo.setEnabled(True)
            else:
                if slot not in CUSTOM_OPTIONAL:
                    combo.addItem("(not available)", None)
                combo.setEnabled(slot in CUSTOM_OPTIONAL)
            combo.blockSignals(False)

        self._schedule_refresh()

    # ── Emotion & refresh ─────────────────────────────────────────────────────

    def _on_slot_changed(self):
        self._schedule_refresh()

    def _set_emotion(self, emotion: str):
        self._selected_emotion = emotion
        self._schedule_refresh()

    def _schedule_refresh(self):
        self._refresh_timer.stop()
        self._refresh_timer.start(120)

    def _do_refresh(self):
        if self._worker and self._worker.isRunning():
            self._worker.done.disconnect()
            self._worker.quit()

        selections = {}
        for slot, combo in self._slot_combos.items():
            data = combo.currentData()
            if data is not None:
                selections[slot] = data

        if not selections:
            self._preview.setSourcePixmap(None)
            self._status_lbl.setText("No layers selected")
            return

        self._status_lbl.setText("Rendering…")
        self._worker = CustomLoadWorker(selections, self._selected_emotion)
        self._worker.done.connect(self._on_preview_ready)
        self._worker.start()

    def _on_preview_ready(self, pix):
        self._preview.setSourcePixmap(pix)
        if pix and not pix.isNull():
            self._status_lbl.setText(f"{pix.width()} × {pix.height()} px")
        else:
            self._status_lbl.setText("Unable to render — check layer selections")

    # ── Save helpers ──────────────────────────────────────────────────────────

    def _current_selections(self) -> dict:
        sel = {}
        for slot, combo in self._slot_combos.items():
            data = combo.currentData()
            if data is not None:
                sel[slot] = data
        return sel

    def _save_preview(self):
        sel = self._current_selections()
        fmt = self._custom_fmt_combo.currentText()

        if fmt == "PSD":
            if not sel:
                QMessageBox.warning(self, "Nothing to Save", "Build a character first.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Layered PSD",
                str(Path.home() / f"character_{self._selected_emotion.lower()}.psd"),
                "Photoshop PSD (*.psd)",
            )
            if not path:
                return
            cw, ch, ldata = extract_custom_layers(sel, self._selected_emotion)
            if ldata:
                write_layered_psd([("", ldata)], cw, ch, path)
                QMessageBox.information(self, "Saved", f"Saved layered PSD to:\n{path}")
            return

        pix = self._preview._source
        if not pix or pix.isNull():
            QMessageBox.warning(self, "Nothing to Save", "Build a character first.")
            return
        ext = "png" if fmt == "PNG" else "jpg"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Image",
            str(Path.home() / f"character_{self._selected_emotion.lower()}.{ext}"),
            "PNG Image (*.png);;JPEG Image (*.jpg)",
        )
        if not path:
            return
        fmt = "JPEG" if path.lower().endswith(".jpg") else "PNG"
        pix.save(path, fmt, 95)

    def _save_all_emotions(self):
        sel = self._current_selections()
        if not sel:
            QMessageBox.warning(self, "Nothing to Save", "Build a character first.")
            return
        fmt = self._custom_fmt_combo.currentText()

        if fmt == "PSD":
            path, _ = QFileDialog.getSaveFileName(
                self, "Save All Emotions as Layered PSD",
                str(Path.home() / "character_all_emotions.psd"),
                "Photoshop PSD (*.psd)",
            )
            if not path:
                return
            self._custom_save_btn.setEnabled(False)
            self._custom_save_all_btn.setEnabled(False)
            self._status_lbl.setText("Building PSD…")
            self._save_worker = SaveCustomEmotionsWorker(sel, Path(path).parent, "PSD")
            self._save_worker.done.connect(
                lambda n, p=path: self._on_custom_psd_done(n, Path(path).parent / "all_emotions.psd", p)
            )
            self._save_worker.start()
            return

        folder = QFileDialog.getExistingDirectory(
            self, "Save All Emotions — Choose Output Folder", str(Path.home())
        )
        if not folder:
            return
        self._custom_save_btn.setEnabled(False)
        self._custom_save_all_btn.setEnabled(False)
        self._status_lbl.setText("Saving all emotions…")
        self._save_worker = SaveCustomEmotionsWorker(sel, Path(folder), fmt)
        self._save_worker.done.connect(lambda n: self._on_custom_save_done(n, folder))
        self._save_worker.start()

    def _on_custom_psd_done(self, saved: int, tmp_path: Path, final_path: str):
        self._custom_save_btn.setEnabled(True)
        self._custom_save_all_btn.setEnabled(True)
        src = self._preview._source
        self._status_lbl.setText(
            f"{src.width() if src else 0} × {src.height() if src else 0} px"
        )
        try:
            if tmp_path.exists() and tmp_path != Path(final_path):
                tmp_path.rename(final_path)
        except Exception:
            pass
        QMessageBox.information(self, "Saved", f"Saved layered PSD to:\n{final_path}")

    def _on_custom_save_done(self, saved: int, folder: str):
        self._custom_save_btn.setEnabled(True)
        self._custom_save_all_btn.setEnabled(True)
        src = self._preview._source
        self._status_lbl.setText(
            f"{src.width() if src else 0} × {src.height() if src else 0} px"
        )
        QMessageBox.information(
            self, "Saved",
            f"Saved {saved} emotion image{'s' if saved != 1 else ''} to:\n{folder}"
        )
