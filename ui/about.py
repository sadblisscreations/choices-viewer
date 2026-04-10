from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from ..config import resource_path
from ..style import ACCENT, BORDER, PANEL_BG, SUBTLE, TEXT


class AboutTab(QWidget):
    def __init__(self):
        super().__init__()

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.setSpacing(0)

        card = QWidget()
        card.setMaximumWidth(520)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(
            f"background: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 12px;"
        )
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(40, 36, 40, 36)
        vbox.setSpacing(0)
        vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Icon
        icon_path = resource_path("icon.png")
        if icon_path.exists():
            icon_lbl = QLabel()
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                pix = pix.scaled(
                    96, 96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            icon_lbl.setPixmap(pix)
            icon_lbl.setStyleSheet("border: none; background: transparent;")
            vbox.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
            vbox.addSpacing(20)

        # App name
        name_lbl = QLabel("sadblisscreations: Choices Tool")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        name_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {TEXT};"
            f" border: none; background: transparent;"
        )
        vbox.addWidget(name_lbl)
        vbox.addSpacing(6)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet(f"color: {BORDER}; border: none; background: {BORDER}; max-height: 1px;")
        vbox.addWidget(sep1)
        vbox.addSpacing(20)

        # Creator line
        by_lbl = QLabel("Created by")
        by_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        by_lbl.setStyleSheet(f"font-size: 12px; color: {SUBTLE}; border: none; background: transparent;")
        vbox.addWidget(by_lbl)
        vbox.addSpacing(4)

        ig_btn = QPushButton("sadblisscreations")
        ig_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ig_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {ACCENT}; font-size: 15px; font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{ color: #b9d1fb; text-decoration: underline; }}
        """)
        ig_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.instagram.com/sadblisscreations/"))
        )
        vbox.addWidget(ig_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        vbox.addSpacing(4)

        ig_hint = QLabel("instagram.com/sadblisscreations")
        ig_hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        ig_hint.setStyleSheet(f"font-size: 11px; color: {SUBTLE}; border: none; background: transparent;")
        vbox.addWidget(ig_hint)
        vbox.addSpacing(24)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {BORDER}; border: none; background: {BORDER}; max-height: 1px;")
        vbox.addWidget(sep2)
        vbox.addSpacing(20)

        # Written by line
        written_lbl = QLabel("Written by sadblisscreations and")
        written_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        written_lbl.setStyleSheet(f"font-size: 12px; color: {SUBTLE}; border: none; background: transparent;")
        vbox.addWidget(written_lbl)
        vbox.addSpacing(4)

        claude_btn = QPushButton("Claude (claude.ai)")
        claude_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        claude_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {ACCENT}; font-size: 13px;
                padding: 0;
            }}
            QPushButton:hover {{ color: #b9d1fb; text-decoration: underline; }}
        """)
        claude_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://claude.ai/"))
        )
        vbox.addWidget(claude_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        vbox.addSpacing(24)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet(f"color: {BORDER}; border: none; background: {BORDER}; max-height: 1px;")
        vbox.addWidget(sep3)
        vbox.addSpacing(16)

        # Effects note
        note_hdr = QLabel("Note on the Effects Tab")
        note_hdr.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        note_hdr.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {TEXT}; border: none; background: transparent;"
        )
        vbox.addWidget(note_hdr)
        vbox.addSpacing(6)

        note_lbl = QLabel(
            "The Effects tab is a hit or miss — some spritesheets will render\n"
            "correctly while others may not display as expected.\n"
            "This is a known limitation."
        )
        note_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet(f"font-size: 11px; color: {SUBTLE}; border: none; background: transparent;")
        vbox.addWidget(note_lbl)

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
