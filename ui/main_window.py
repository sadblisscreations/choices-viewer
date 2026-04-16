from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QMainWindow, QMessageBox, QTabWidget,
)

from ..assets import find_characters, discover_custom_items, discover_portrait_layers, discover_spritesheets, discover_ccbi_scenes
from ..config import load_config, save_config
from ..style import BASE_STYLE
from .dialogs import FolderPickerDialog
from .characters import CharactersTab
from .custom import CustomBuilderTab
from .effects import EffectsTab
from .scenes import ScenesTab
from .about import AboutTab


class MainWindow(QMainWindow):
    def __init__(self, assets: Path, characters: list, custom_items: dict, sheets: list, ccbi_scenes: list):
        super().__init__()
        self._assets = assets

        self.setWindowTitle("sadblisscreations: Choices Tool")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumSize(900, 600)
        self.resize(1440, 860)
        self.setStyleSheet(BASE_STYLE)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        self._chars_tab   = CharactersTab(assets, characters)
        self._custom_tab  = CustomBuilderTab(assets, custom_items)
        self._effects_tab = EffectsTab(assets, sheets)
        self._scenes_tab  = ScenesTab(assets, ccbi_scenes)
        self._about_tab   = AboutTab()

        tabs.addTab(self._chars_tab,   "Characters")
        tabs.addTab(self._custom_tab,  "Custom")
        tabs.addTab(self._effects_tab, "Effects")
        tabs.addTab(self._scenes_tab,  "Scenes")
        tabs.addTab(self._about_tab,   "About")

        self._chars_tab.folder_change_requested.connect(self._change_folder)
        self.setCentralWidget(tabs)

    def _change_folder(self):
        cfg = load_config()
        dlg = FolderPickerDialog(initial_path=cfg.get("dlc_path", ""))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        assets = dlg.chosen_assets_path()
        if assets is None:
            return
        save_config({"dlc_path": dlg.chosen_raw_path()})
        chars = find_characters(assets)
        if not chars:
            QMessageBox.warning(
                self, "No Characters Found",
                "No portrait files were found in that folder.\n"
                "Please check you selected the correct DLC cache directory."
            )
            return
        self._assets = assets
        self._chars_tab.refresh(assets, chars)
        self._custom_tab.update_assets(
            assets,
            {**discover_custom_items(assets), **discover_portrait_layers(assets)},
        )
        self._effects_tab.update_assets(assets, discover_spritesheets(assets))
        self._scenes_tab.update_assets(assets, discover_ccbi_scenes(assets))
