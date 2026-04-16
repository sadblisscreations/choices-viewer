from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ..config import resource_path
from ..style import BG, TEXT


class AboutTab(QWidget):
    def __init__(self):
        super().__init__()

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(0)

        # Classic raised About box using QWidget + explicit border
        box = QWidget()
        box.setMaximumWidth(520)
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        box.setStyleSheet(
            "background: " + BG + "; "
            "border-top: 2px solid #5c5c5c; "
            "border-left: 2px solid #5c5c5c; "
            "border-right: 2px solid #0a0a0a; "
            "border-bottom: 2px solid #0a0a0a;"
        )

        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(8)
        vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Icon
        icon_path = resource_path("icon.png")
        if icon_path.exists():
            icon_lbl = QLabel()
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                pix = pix.scaled(
                    64, 64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            icon_lbl.setPixmap(pix)
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            vbox.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        # App name
        name_lbl = QLabel("Choices Tool")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        name_lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: " + TEXT + "; border: none; background: transparent;"
        )
        vbox.addWidget(name_lbl)

        # Sunken separator
        from . import separator
        vbox.addWidget(separator())

        # Creator line
        by_lbl = QLabel("Created by sadblisscreations")
        by_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        by_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; border: none; background: transparent;")
        vbox.addWidget(by_lbl)

        ig_btn = QPushButton("instagram.com/sadblisscreations")
        ig_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ig_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #4fc1ff; font-size: 11px;
                padding: 0;
            }
            QPushButton:hover { color: #ffffff; text-decoration: underline; }
        """)
        ig_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.instagram.com/sadblisscreations/"))
        )
        vbox.addWidget(ig_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Sunken separator
        vbox.addWidget(separator())

        written_lbl = QLabel("Written by sadblisscreations and Claude")
        written_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        written_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; border: none; background: transparent;")
        vbox.addWidget(written_lbl)

        claude_btn = QPushButton("claude.ai")
        claude_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        claude_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #4fc1ff; font-size: 11px;
                padding: 0;
            }
            QPushButton:hover { color: #ffffff; text-decoration: underline; }
        """)
        claude_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://claude.ai/"))
        )
        vbox.addWidget(claude_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Sunken separator
        vbox.addWidget(separator())

        # Effects note
        note_hdr = QLabel("Note on the Spritesheets Tab")
        note_hdr.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        note_hdr.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: " + TEXT + "; border: none; background: transparent;"
        )
        vbox.addWidget(note_hdr)

        note_lbl = QLabel(
            "The Spritesheets tab is a hit or miss — some spritesheets will render\n"
            "correctly while others may not display as expected.\n"
            "This is a known limitation."
        )
        note_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet("font-size: 11px; color: " + TEXT + "; border: none; background: transparent;")
        vbox.addWidget(note_lbl)

        outer.addWidget(box, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
