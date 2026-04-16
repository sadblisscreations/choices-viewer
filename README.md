```text
███████╗  █████╗  ██████╗ ██████╗ ██╗     ██╗███████╗███████╗
██╔════╝ ██╔══██╗ ██╔══██╗██╔══██╗██║     ██║██╔════╝██╔════╝
███████╗ ███████║ ██║  ██║██████╔╝██║     ██║███████╗███████╗
╚════██║ ██╔══██║ ██║  ██║██╔══██╗██║     ██║╚════██║╚════██║
███████║ ██║  ██║ ██████╔╝██████╔╝███████╗██║███████║███████║
╚══════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝╚══════╝╚══════╝

 ██████╗ ██████╗ ███████╗ █████╗ ████████╗██╗ ██████╗ ███╗   ██╗███████╗
██╔════╝ ██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝
██║      ██████╔╝█████╗  ███████║   ██║   ██║██║   ██║██╔██╗ ██║███████╗
██║      ██╔══██╗██╔══╝  ██╔══██║   ██║   ██║██║   ██║██║╚██╗██║╚════██║
╚██████╗ ██║  ██║███████╗██║  ██║   ██║   ██║╚██████╔╝██║ ╚████║███████║
 ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
```

# Choices Viewer

A desktop tool for browsing and exporting assets from the mobile game *Choices: Stories You Play*. Point it at your local DLC cache folder and it will parse the game's spritesheet atlases so you can preview and save characters, custom items, and effects.

## Features

- **Characters** - browse character portraits with emotion variants
- **Custom** - build and preview custom character outfits by mixing and matching slots (hair, hat, eyes, mouth, body, etc.)
- **Effects** - view and play back animated spritesheets frame by frame with adjustable FPS
- Export anything as PNG, GIF, or layered PSD

## Requirements

- Python 3.10+
- The game's DLC cache folder on your local machine

## Setup

```bash
pip install -r requirements.txt
```

## Running

Run from the parent directory of the `choices_viewer` folder:

```bash
python -m choices_viewer
```

On first launch you will be prompted to select your DLC cache folder. The path is saved so you only need to do this once. You can change it later from the Characters tab.

## Building a standalone executable

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name choices-viewer choices_viewer/__main__.py
```

The executable will be in the `dist/` folder.

## Contributors

- [sadblisscreations](https://github.com/sadblisscreations)
- [Claude](https://claude.ai) (Books tab / branching story graph, parser improvements, UI polish)
- [Kimi](https://github.com/moonshot-ai) (Books tab / branching story graph, parser improvements, UI polish)
