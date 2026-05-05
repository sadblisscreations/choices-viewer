#!/usr/bin/env python3
"""
Choices: Stories You Play — Character Viewer
Entry point: python -m choices_viewer
"""

import os
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from .config import load_config, resource_path, save_config
from .assets import validate_dlc_path
from .ui.style import BASE_STYLE
from .ui.dialogs import FolderPickerDialog, LoadingDialog
from .ui.main_window import MainWindow


def main():
    # Enable proper HiDPI / 4K scaling before creating the application
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(BASE_STYLE)
    app.setApplicationName("sadblisscreations: Choices Tool")

    icon_path = resource_path("icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    cfg        = load_config()
    saved_path = cfg.get("dlc_path", "")
    assets     = validate_dlc_path(Path(saved_path)) if saved_path else None

    if assets is None:
        dlg = FolderPickerDialog(initial_path=saved_path)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        assets = dlg.chosen_assets_path()
        if assets is None:
            sys.exit(0)
        save_config({"dlc_path": dlg.chosen_raw_path()})

    loading = LoadingDialog(assets)
    if icon_path.exists():
        loading.setWindowIcon(QIcon(str(icon_path)))
    if loading.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)
    results = loading.results() or {}
    characters   = results.get("characters", [])
    custom_items = results.get("custom_items", {})
    sheets       = results.get("sheets", [])
    ccbi_scenes  = results.get("ccbi_scenes", [])
    books        = results.get("books", [])
    char_books   = results.get("char_books", {})

    if not characters and not custom_items and not sheets and not ccbi_scenes and not books:
        QMessageBox.critical(
            None, "No Content Found",
            f"No portrait files were found in:\n{assets}\n\n"
            "Please check you selected the correct DLC cache folder."
        )
        sys.exit(1)

    win = MainWindow(assets, characters, custom_items, sheets, ccbi_scenes, books, char_books)
    if icon_path.exists():
        win.setWindowIcon(QIcon(str(icon_path)))
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
