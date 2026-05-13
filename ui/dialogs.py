from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QProgressBar, QPushButton, QVBoxLayout,
)

from ..assets import validate_dlc_path, portrait_dirs
from .style import BASE_STYLE, TEXT


class FolderPickerDialog(QDialog):
    def __init__(self, initial_path: str = ""):
        super().__init__()
        self.setWindowTitle("Choices Tool — Setup")
        self.setStyleSheet(BASE_STYLE)
        self.setMinimumWidth(480)
        self.resize(560, 0)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._assets_path = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Choices Tool")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: " + TEXT + ";")
        subtitle = QLabel("Composite portrait viewer — every character, every emotion")
        subtitle.setStyleSheet("font-size: 11px; color: " + TEXT + "; margin-bottom: 8px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        instr = QLabel(
            "Select your <b>Choices DLC cache folder</b>.<br>"
            "This is the folder you copied from your device — it should contain<br>"
            "an <code>assets</code> subfolder with <code>portraits</code> inside."
        )
        instr.setWordWrap(True)
        instr.setStyleSheet("color: " + TEXT + "; font-size: 11px;")
        layout.addWidget(instr)

        help_btn = QPushButton("Not sure where to find the DLC cache folder? Click here for a guide.")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #4fc1ff; font-size: 11px;
                padding: 0 0 6px 0; text-align: left;
            }
            QPushButton:hover { color: #ffffff; text-decoration: underline; }
        """)
        help_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(
            "https://www.reddit.com/r/Choices/comments/bd1fa9/comment/ekvg388/"
            "?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button"
        )))
        layout.addWidget(help_btn)

        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self.path_edit = QLineEdit(initial_path)
        self.path_edit.setPlaceholderText("Path to your DLC cache folder…")
        self.path_edit.textChanged.connect(self._on_path_changed)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 11px; margin-top: 2px; margin-bottom: 8px; color: " + TEXT + ";")
        self.status_lbl.setMinimumHeight(18)
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.reject)
        self.open_btn = QPushButton("Open Viewer")
        self.open_btn.setObjectName("primary")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.accept)
        btn_row.addWidget(quit_btn)
        btn_row.addWidget(self.open_btn)
        layout.addLayout(btn_row)

        if initial_path:
            self._on_path_changed(initial_path)

    def _browse(self):
        start = self.path_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Choices DLC Cache Folder", start)
        if chosen:
            self.path_edit.setText(chosen)

    def _on_path_changed(self, text: str):
        if not text.strip():
            self._set_status("", valid=None)
            self.open_btn.setEnabled(False)
            self._assets_path = None
            return
        assets = validate_dlc_path(Path(text.strip()))
        if assets is None:
            self._set_status("✗  Folder not recognised — expected an 'assets/portraits' structure inside.", valid=False)
            self.open_btn.setEnabled(False)
            self._assets_path = None
        else:
            count = sum(1 for d in portrait_dirs(assets) if d.exists() for _ in d.glob("*.plist"))
            self._set_status(f"✓  Valid DLC folder — {count} portrait files found.", valid=True)
            self.open_btn.setEnabled(True)
            self._assets_path = assets

    def _set_status(self, text: str, valid):
        colour = "#89d185" if valid is True else ("#f44747" if valid is False else TEXT)
        self.status_lbl.setStyleSheet(
            "font-size: 11px; margin-top: 2px; margin-bottom: 8px; color: " + colour + ";"
        )
        self.status_lbl.setText(text)

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    def chosen_assets_path(self):
        return self._assets_path

    def chosen_raw_path(self) -> str:
        return self.path_edit.text().strip()


class DiscoveryWorker(QThread):
    progress = pyqtSignal(str, int, int)   # stage, done, total
    finished_loading = pyqtSignal(object)  # dict of results, or None on error
    error = pyqtSignal(str)

    def __init__(self, assets: Path):
        super().__init__()
        self._assets = assets

    def run(self):
        from ..assets import (
            discover_books, discover_character_books, discover_custom_items,
            discover_portrait_layers, discover_ccbi_scenes,
            discover_scene_books,
            find_characters,
        )
        try:
            cb = lambda stage, done, total: self.progress.emit(stage, done, total)

            self.progress.emit("Finding characters", 0, 0)
            characters = find_characters(self._assets)

            self.progress.emit("Discovering custom items", 0, 0)
            custom = discover_custom_items(self._assets)

            self.progress.emit("Parsing portrait atlases", 0, 0)
            portraits = discover_portrait_layers(self._assets, on_progress=cb)
            custom_items = {**custom, **portraits}

            self.progress.emit("Validating scenes", 0, 0)
            ccbi_scenes = discover_ccbi_scenes(self._assets, on_progress=cb)

            self.progress.emit("Discovering books", 0, 0)
            books_root = self._assets.parent / "books"
            books = discover_books(books_root)

            self.progress.emit("Indexing book characters", 0, 0)
            char_books = discover_character_books(books_root, on_progress=cb)

            self.progress.emit("Indexing book scenes", 0, 0)
            scene_books = discover_scene_books(books_root, on_progress=cb)

            self.finished_loading.emit({
                "characters":   characters,
                "custom_items": custom_items,
                "ccbi_scenes":  ccbi_scenes,
                "books":        books,
                "char_books":   char_books,
                "scene_books":  scene_books,
            })
        except Exception as e:
            self.error.emit(str(e))


class LoadingDialog(QDialog):
    def __init__(self, assets: Path):
        super().__init__()
        self.setWindowTitle("Choices Tool — Loading")
        self.setStyleSheet(BASE_STYLE)
        self.setMinimumWidth(440)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint
        )
        self._results = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Loading your DLC cache…")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: " + TEXT + ";")
        layout.addWidget(title)

        self._note = QLabel(
            "First-time launch parses every portrait, scene, and spritesheet.\n"
            "Subsequent launches will be much faster — results are cached."
        )
        self._note.setWordWrap(True)
        self._note.setStyleSheet("font-size: 11px; color: " + TEXT + ";")
        layout.addWidget(self._note)

        self._stage_lbl = QLabel("Starting…")
        self._stage_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; margin-top: 6px;")
        layout.addWidget(self._stage_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)   # busy spinner until first real progress
        self._bar.setTextVisible(True)
        layout.addWidget(self._bar)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("font-size: 10px; color: #808080;")
        layout.addWidget(self._count_lbl)

        self._worker = DiscoveryWorker(assets)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_loading.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, stage: str, done: int, total: int):
        self._stage_lbl.setText(stage + "…")
        if total > 0:
            self._bar.setRange(0, total)
            self._bar.setValue(done)
            self._count_lbl.setText(f"{done} / {total}")
        else:
            self._bar.setRange(0, 0)
            self._count_lbl.setText("")

    def _on_done(self, results):
        self._results = results
        self.accept()

    def _on_error(self, msg: str):
        self._stage_lbl.setText(f"Error: {msg}")
        self._bar.setRange(0, 1)
        self._bar.setValue(0)

    def results(self):
        return self._results

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )
