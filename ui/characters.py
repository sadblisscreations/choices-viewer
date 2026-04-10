import re
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from ..plist_parser import parse_plist
from ..psd import extract_sprite_layers, write_layered_psd
from ..workers import LoadWorker, SaveAllWorker
from ..style import ACCENT, EMOTION_COLORS, SUBTLE, TEXT
from . import separator


class EmotionCard(QWidget):
    CARD_WIDTH = 200

    def __init__(self, emotion: str, pixmap, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 10)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        img = QLabel()
        img.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        if pixmap and not pixmap.isNull():
            img.setPixmap(pixmap.scaledToWidth(self.CARD_WIDTH, Qt.TransformationMode.SmoothTransformation))
        else:
            img.setText("—")
            img.setStyleSheet(f"color: {SUBTLE}; font-size: 24px;")
            img.setFixedSize(self.CARD_WIDTH, self.CARD_WIDTH)

        colour = EMOTION_COLORS.get(emotion, ACCENT)
        badge = QLabel(emotion)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: {colour}; font-size: 10px; font-weight: bold;"
            f" letter-spacing: 1.5px; padding: 3px 6px;"
            f" border: 1px solid {colour}; border-radius: 3px;"
        )
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        lay.addWidget(img)
        lay.addWidget(badge, alignment=Qt.AlignmentFlag.AlignHCenter)


class CharacterPanel(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._root = QWidget()
        self._vbox = QVBoxLayout(self._root)
        self._vbox.setContentsMargins(20, 20, 20, 20)
        self._vbox.setSpacing(16)
        self._vbox.addStretch()
        self.setWidget(self._root)
        self._show_placeholder()

    def show_loading(self, name: str):
        self._clear()
        self._insert_title(name)
        lbl = QLabel("Loading…")
        lbl.setStyleSheet(f"color: {SUBTLE}; font-size: 13px; padding: 20px;")
        self._vbox.insertWidget(1, lbl)

    def show_emotions(self, name: str, results: list):
        self._clear()
        self._insert_title(name)
        row_w = QWidget()
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        if results:
            for emotion, pix in results:
                row.addWidget(EmotionCard(emotion, pix))
        else:
            lbl = QLabel("No renderable layers found for this character.")
            lbl.setStyleSheet(f"color: {SUBTLE}; font-size: 13px; padding: 20px;")
            row.addWidget(lbl)
        row.addStretch()
        self._vbox.insertWidget(1, row_w)

    def _show_placeholder(self):
        lbl = QLabel("← Select a character to view")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {SUBTLE}; font-size: 14px;")
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._vbox.insertWidget(0, lbl)

    def _insert_title(self, name: str):
        title = QLabel(name)
        title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {TEXT}; padding-bottom: 4px;")
        self._vbox.insertWidget(0, separator())
        self._vbox.insertWidget(0, title)

    def _clear(self):
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class CharactersTab(QWidget):
    folder_change_requested = pyqtSignal()

    def __init__(self, assets: Path, characters: list):
        super().__init__()
        self._assets          = assets
        self._all             = characters
        self._worker          = None
        self._save_worker     = None
        self._current_name    = ""
        self._current_results = []   # [(emotion, QPixmap)]
        self._current_png     = None
        self._current_plist   = None
        self._build_ui()
        self._populate(characters)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar = QWidget()
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(400)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(10, 10, 10, 10)
        sb.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search characters…")
        self._search.textChanged.connect(self._on_search)

        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet(f"font-size: 11px; color: {SUBTLE}; padding: 0 4px;")

        self._list_w = QListWidget()
        self._list_w.setUniformItemSizes(True)
        self._list_w.currentItemChanged.connect(self._on_select)

        change_btn = QPushButton("Change DLC Folder…")
        change_btn.clicked.connect(self.folder_change_requested.emit)

        sb.addWidget(self._search)
        sb.addWidget(self._count_lbl)
        sb.addWidget(self._list_w)
        sb.addWidget(change_btn)
        sb.addWidget(separator())

        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("Format:")
        fmt_lbl.setStyleSheet(f"font-size: 11px; color: {SUBTLE};")
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["PNG", "JPEG", "PSD"])
        self._fmt_combo.setFixedWidth(80)
        fmt_row.addWidget(fmt_lbl)
        fmt_row.addWidget(self._fmt_combo)
        fmt_row.addStretch()
        sb.addLayout(fmt_row)

        self._save_btn = QPushButton("Save Character…")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_current)
        sb.addWidget(self._save_btn)

        self._save_all_btn = QPushButton("Save All Characters…")
        self._save_all_btn.clicked.connect(self._save_all)
        sb.addWidget(self._save_all_btn)

        self._save_progress_lbl = QLabel("")
        self._save_progress_lbl.setStyleSheet(f"font-size: 10px; color: {SUBTLE};")
        self._save_progress_lbl.setWordWrap(True)
        sb.addWidget(self._save_progress_lbl)

        self._panel = CharacterPanel()

        splitter.addWidget(sidebar)
        splitter.addWidget(self._panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 900])
        layout.addWidget(splitter)

    def refresh(self, assets: Path, characters: list):
        self._assets = assets
        self._all    = characters
        self._search.clear()
        self._populate(characters)

    def _populate(self, chars: list):
        self._list_w.blockSignals(True)
        self._list_w.clear()
        for name, png, plist in chars:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, (name, png, plist))
            self._list_w.addItem(item)
        n = len(chars)
        self._count_lbl.setText(f"{n} character{'s' if n != 1 else ''}")
        self._list_w.blockSignals(False)
        if self._list_w.count():
            self._list_w.setCurrentRow(0)

    def _on_search(self, text: str):
        t = text.lower()
        self._populate([(n, p, pl) for n, p, pl in self._all if t in n.lower()])

    def _on_select(self, current, _prev=None):
        if current is None:
            return
        name, png, plist = current.data(Qt.ItemDataRole.UserRole)
        if self._worker and self._worker.isRunning():
            self._worker.done.disconnect()
            self._worker.quit()
        self._panel.show_loading(name)
        self._current_png   = png
        self._current_plist = plist
        self._worker = LoadWorker(name, png, plist)
        self._worker.done.connect(self._on_loaded)
        self._worker.start()

    def _on_loaded(self, name: str, results: list):
        self._current_name    = name
        self._current_results = results
        self._panel.show_emotions(name, results)
        self._save_btn.setEnabled(bool(results))

    # ── Save current character ────────────────────────────────────────────────

    def _save_current(self):
        if not self._current_results:
            return
        fmt  = self._fmt_combo.currentText()
        safe = re.sub(r'[<>:"/\\|?*]', "_", self._current_name)

        if fmt == "PSD":
            path, _ = QFileDialog.getSaveFileName(
                self, f"Save '{self._current_name}' as PSD",
                str(Path.home() / f"{safe}.psd"), "Photoshop PSD (*.psd)"
            )
            if not path:
                return
            sprites = parse_plist(self._current_plist)
            groups, cw, ch = [], 0, 0
            for emotion, _ in self._current_results:
                w, h, ldata = extract_sprite_layers(self._current_png, sprites, emotion)
                if ldata:
                    cw = max(cw, w); ch = max(ch, h)
                    groups.append((emotion.title(), ldata))
            if groups:
                write_layered_psd(groups, cw, ch, path)
            QMessageBox.information(self, "Saved", f"Saved layered PSD to:\n{path}")
        else:
            folder = QFileDialog.getExistingDirectory(
                self, f"Save '{self._current_name}' Sprites", str(Path.home())
            )
            if not folder:
                return
            ext   = "png" if fmt == "PNG" else "jpg"
            out   = Path(folder)
            saved = 0
            for emotion, pix in self._current_results:
                if pix and not pix.isNull():
                    pix.save(str(out / f"{safe}_{emotion.lower()}.{ext}"), fmt, 95)
                    saved += 1
            QMessageBox.information(
                self, "Saved",
                f"Saved {saved} image{'s' if saved != 1 else ''} to:\n{folder}"
            )

    # ── Save all characters ───────────────────────────────────────────────────

    def _save_all(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Save All Characters — Choose Output Folder", str(Path.home())
        )
        if not folder:
            return
        fmt = self._fmt_combo.currentText()
        self._save_all_btn.setEnabled(False)
        self._save_progress_lbl.setText("Starting…")
        self._save_worker = SaveAllWorker(self._all, Path(folder), fmt)
        self._save_worker.progress.connect(self._on_save_progress)
        self._save_worker.finished_saving.connect(self._on_save_all_done)
        self._save_worker.start()

    def _on_save_progress(self, done: int, total: int, name: str):
        self._save_progress_lbl.setText(f"Saving {done + 1}/{total}:\n{name}")

    def _on_save_all_done(self, saved: int, errors: int):
        self._save_all_btn.setEnabled(True)
        self._save_progress_lbl.setText("")
        msg = f"Saved {saved} image{'s' if saved != 1 else ''}."
        if errors:
            msg += f"\n({errors} character{'s' if errors != 1 else ''} had errors)"
        QMessageBox.information(self, "Save All Complete", msg)
