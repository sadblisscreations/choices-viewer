import re
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from PyQt6.QtWidgets import QAbstractItemView, QStyledItemDelegate

from ..parsers.plist_parser import parse_plist
from ..psd import extract_sprite_layers, write_layered_psd
from ..workers import LoadWorker, SaveAllWorker
from .style import EMOTION_COLORS, TEXT
from . import separator


class _CurrentMarkerDelegate(QStyledItemDelegate):
    """Bullets and bolds the row that matches the combo's currentIndex —
    distinct from the hover/keyboard-focus highlight so the user can see
    at a glance which option they previously selected."""

    def __init__(self, combo):
        super().__init__(combo)
        self._combo = combo

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if index.row() == self._combo.currentIndex():
            option.text = "● " + option.text
            f = option.font
            f.setBold(True)
            option.font = f


class HighlightingComboBox(QComboBox):
    """Scrolls to + highlights the current selection on popup, and uses
    a delegate to mark the previously-chosen item with a bullet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view().setItemDelegate(_CurrentMarkerDelegate(self))

    def showPopup(self):
        super().showPopup()
        idx = self.currentIndex()
        if idx < 0:
            return
        view = self.view()
        model_idx = self.model().index(idx, self.modelColumn())
        view.setCurrentIndex(model_idx)
        view.scrollTo(model_idx, QAbstractItemView.ScrollHint.PositionAtCenter)


class EmotionCard(QWidget):
    CARD_WIDTH = 200

    def __init__(self, emotion: str, pixmap, on_save=None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.setStyleSheet(
            "background: #1e1e1e; "
            "border-top: 2px solid #0a0a0a; "
            "border-left: 2px solid #0a0a0a; "
            "border-right: 2px solid #5c5c5c; "
            "border-bottom: 2px solid #5c5c5c;"
        )

        img = QLabel()
        img.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        img.setStyleSheet("border: none; background: #1e1e1e;")
        if pixmap and not pixmap.isNull():
            img.setPixmap(pixmap.scaledToWidth(self.CARD_WIDTH, Qt.TransformationMode.SmoothTransformation))
        else:
            img.setText("—")
            img.setStyleSheet("color: #808080; font-size: 18px; border: none; background: #1e1e1e;")
            img.setFixedSize(self.CARD_WIDTH, self.CARD_WIDTH)

        colour = EMOTION_COLORS.get(emotion, "#4fc1ff")
        badge = QLabel(emotion)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: {colour}; font-size: 11px; font-weight: bold;"
            f" letter-spacing: 1px; padding: 2px 4px;"
            f" border: 1px solid {colour}; background: #1e1e1e;"
        )
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        lay.addWidget(img)
        lay.addWidget(badge, alignment=Qt.AlignmentFlag.AlignHCenter)

        if on_save:
            save_btn = QPushButton("Save")
            save_btn.setFixedSize(48, 20)
            save_btn.setStyleSheet(
                "QPushButton { background: #2b2b2b; color: #e0e0e0; "
                "border-top: 1px solid #5c5c5c; border-left: 1px solid #5c5c5c; "
                "border-right: 1px solid #0a0a0a; border-bottom: 1px solid #0a0a0a; "
                "font-size: 10px; padding: 0; }"
                "QPushButton:pressed { border-top: 1px solid #0a0a0a; border-left: 1px solid #0a0a0a; "
                "border-right: 1px solid #5c5c5c; border-bottom: 1px solid #5c5c5c; }"
            )
            save_btn.clicked.connect(lambda _checked, e=emotion: on_save(e))
            lay.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignHCenter)


class CharacterPanel(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._root = QWidget()
        self._vbox = QVBoxLayout(self._root)
        self._vbox.setContentsMargins(12, 12, 12, 12)
        self._vbox.setSpacing(10)
        self._vbox.addStretch()
        self.setWidget(self._root)
        self._show_placeholder()

    def show_loading(self, name: str):
        self._clear()
        self._insert_title(name)
        lbl = QLabel("Loading…")
        lbl.setStyleSheet("color: #808080; font-size: 12px; padding: 12px; background: transparent;")
        self._vbox.insertWidget(1, lbl)

    def show_emotions(self, name: str, results: list, on_save=None):
        self._clear()
        self._insert_title(name)
        row_w = QWidget()
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        if results:
            for emotion, pix in results:
                row.addWidget(EmotionCard(emotion, pix, on_save))
        else:
            lbl = QLabel("No renderable layers found for this character.")
            lbl.setStyleSheet("color: #808080; font-size: 12px; padding: 12px; background: transparent;")
            row.addWidget(lbl)
        row.addStretch()
        self._vbox.insertWidget(1, row_w)

    def _show_placeholder(self):
        lbl = QLabel("← Select a character to view")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #808080; font-size: 13px; background: transparent;")
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._vbox.insertWidget(0, lbl)

    def _insert_title(self, name: str):
        title = QLabel(name)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: " + TEXT + "; padding-bottom: 2px; background: transparent;")
        self._vbox.insertWidget(0, separator())
        self._vbox.insertWidget(0, title)

    def _clear(self):
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class CharactersTab(QWidget):
    folder_change_requested = pyqtSignal()

    def __init__(self, assets: Path, characters: list, char_books: dict | None = None):
        super().__init__()
        self._assets          = assets
        self._all             = characters
        self._char_books      = char_books or {}   # {book_dir_name: set(char_name_lower)}
        self._worker          = None
        self._save_worker     = None
        self._current_name    = ""
        self._current_results = []   # [(emotion, QPixmap)]
        self._current_png     = None
        self._current_plist   = None
        self._build_ui()
        self._rebuild_book_combo()
        self._apply_filters()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar = QWidget()
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(400)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(8, 8, 8, 8)
        sb.setSpacing(6)

        self._book_combo = HighlightingComboBox()
        self._book_combo.setMaxVisibleItems(20)
        self._book_combo.currentIndexChanged.connect(self._apply_filters)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search characters…")
        self._search.textChanged.connect(self._apply_filters)

        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; padding: 0 2px; background: transparent;")

        self._list_w = QListWidget()
        self._list_w.setUniformItemSizes(True)
        self._list_w.currentItemChanged.connect(self._on_select)

        change_btn = QPushButton("Change DLC Folder…")
        change_btn.clicked.connect(self.folder_change_requested.emit)

        sb.addWidget(self._book_combo)
        sb.addWidget(self._search)
        sb.addWidget(self._count_lbl)
        sb.addWidget(self._list_w)
        sb.addWidget(change_btn)
        sb.addWidget(separator())

        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("Format:")
        fmt_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; background: transparent;")
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
        self._save_progress_lbl.setStyleSheet("font-size: 10px; color: " + TEXT + "; background: transparent;")
        self._save_progress_lbl.setWordWrap(True)
        sb.addWidget(self._save_progress_lbl)

        self._panel = CharacterPanel()

        splitter.addWidget(sidebar)
        splitter.addWidget(self._panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 900])
        layout.addWidget(splitter)

    @staticmethod
    def _portrait_stem(plist: Path) -> str:
        """Version-less portrait stem (matches the keys used by the per-book
        portrait-reference index). E.g. `portrait_anime_main_jake-v01` →
        `portrait_anime_main_jake`."""
        return plist.stem.split("-v")[0]

    def _books_for(self, plist: Path) -> set:
        stem = self._portrait_stem(plist)
        return {b for b, stems in self._char_books.items() if stem in stems}

    def refresh(self, assets: Path, characters: list, char_books: dict | None = None):
        self._assets = assets
        self._all    = characters
        if char_books is not None:
            self._char_books = char_books
        self._search.clear()
        self._rebuild_book_combo()
        self._apply_filters()

    def _rebuild_book_combo(self):
        per_book_count: dict = {}
        unassigned = 0
        for _n, _p, pl in self._all:
            bs = self._books_for(pl)
            if not bs:
                unassigned += 1
                continue
            for b in bs:
                per_book_count[b] = per_book_count.get(b, 0) + 1

        self._book_combo.blockSignals(True)
        self._book_combo.clear()
        self._book_combo.addItem(f"All Books ({len(self._all)})", "")
        for b in sorted(per_book_count.keys()):
            display = b.removeprefix("book_").replace("_", " ").title()
            self._book_combo.addItem(f"{display} ({per_book_count[b]})", b)
        if unassigned:
            self._book_combo.addItem(f"— Unassigned ({unassigned})", "__unassigned__")
        self._book_combo.blockSignals(False)

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

    def _apply_filters(self, *_):
        book = self._book_combo.currentData() or ""
        t = self._search.text().lower()
        def book_ok(pl):
            if not book:
                return True
            if book == "__unassigned__":
                return not self._books_for(pl)
            return book in self._books_for(pl)
        filtered = [
            (n, p, pl) for n, p, pl in self._all
            if book_ok(pl) and (not t or t in n.lower())
        ]
        self._populate(filtered)

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
        self._panel.show_emotions(name, results, self._save_emotion)
        self._save_btn.setEnabled(bool(results))

    def _save_emotion(self, emotion: str):
        pix = None
        for em, p in self._current_results:
            if em == emotion:
                pix = p
                break
        if not pix or pix.isNull():
            return
        fmt  = self._fmt_combo.currentText()
        safe = re.sub(r'[<>:"/\\|?*]', "_", f"{self._current_name}_{emotion}")

        if fmt == "PSD":
            path, _ = QFileDialog.getSaveFileName(
                self, f"Save '{self._current_name}' {emotion} as PSD",
                str(Path.home() / f"{safe}.psd"), "Photoshop PSD (*.psd)"
            )
            if not path:
                return
            sprites = parse_plist(self._current_plist)
            w, h, ldata = extract_sprite_layers(self._current_png, sprites, emotion)
            if ldata:
                write_layered_psd([("", ldata)], w, h, path)
            QMessageBox.information(self, "Saved", f"Saved layered PSD to:\n{path}")
        else:
            ext = "png" if fmt == "PNG" else "jpg"
            path, _ = QFileDialog.getSaveFileName(
                self, f"Save '{self._current_name}' {emotion}",
                str(Path.home() / f"{safe}.{ext}"),
                "PNG Image (*.png);;JPEG Image (*.jpg)"
            )
            if not path:
                return
            out_fmt = "JPEG" if path.lower().endswith(".jpg") else "PNG"
            pix.save(path, out_fmt, 95)
            QMessageBox.information(self, "Saved", f"Saved image to:\n{path}")

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
