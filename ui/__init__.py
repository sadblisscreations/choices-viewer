from PyQt6.QtWidgets import QFrame

from ..style import BORDER


def separator() -> QFrame:
    """Return a styled horizontal separator line."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: {BORDER};")
    return f
