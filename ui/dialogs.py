from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from ..assets import validate_dlc_path, portrait_dirs
from ..style import ACCENT, GREEN, SUBTLE, TEXT, BASE_STYLE


class FolderPickerDialog(QDialog):
    def __init__(self, initial_path: str = ""):
        super().__init__()
        self.setWindowTitle("sadblisscreations: Choices Tool — Setup")
        self.setStyleSheet(BASE_STYLE)
        self.setMinimumWidth(460)
        self.resize(560, 0)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._assets_path = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 28)
        layout.setSpacing(0)

        title = QLabel("sadblisscreations: Choices Tool")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #cdd6f4;")
        subtitle = QLabel("Composite portrait viewer — every character, every emotion")
        subtitle.setStyleSheet(f"font-size: 12px; color: {SUBTLE}; margin-bottom: 28px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        instr = QLabel(
            "Select your <b>Choices DLC cache folder</b>.<br>"
            "This is the folder you copied from your device — it should contain<br>"
            "an <code>assets</code> subfolder with <code>portraits</code> inside."
        )
        instr.setWordWrap(True)
        instr.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; line-height: 1.6;"
            f" background: #313244; border-radius: 6px; padding: 14px 16px; margin-bottom: 10px;"
        )
        layout.addWidget(instr)

        help_btn = QPushButton("Not sure where to find the DLC cache folder?  Click here for a guide.")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {ACCENT}; font-size: 11px;
                padding: 0 0 16px 0; text-align: left;
            }}
            QPushButton:hover {{ color: #b9d1fb; text-decoration: underline; }}
        """)
        help_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(
            "https://www.reddit.com/r/Choices/comments/bd1fa9/comment/ekvg388/"
            "?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button"
        )))
        layout.addWidget(help_btn)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_edit = QLineEdit(initial_path)
        self.path_edit.setPlaceholderText("Path to your DLC cache folder…")
        self.path_edit.textChanged.connect(self._on_path_changed)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"font-size: 11px; margin-top: 6px; margin-bottom: 20px;")
        self.status_lbl.setMinimumHeight(20)
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
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
        colour = GREEN if valid is True else ("#f38ba8" if valid is False else SUBTLE)
        self.status_lbl.setStyleSheet(
            f"font-size: 11px; margin-top: 6px; margin-bottom: 20px; color: {colour};"
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
