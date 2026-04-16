from PyQt6.QtWidgets import QFrame


def separator() -> QFrame:
    """Return a classic Windows 98 horizontal etched separator line."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(
        "border-top: 1px solid #0a0a0a; "
        "border-bottom: 1px solid #5c5c5c; "
        "background: transparent;"
    )
    return f
