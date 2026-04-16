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

A desktop tool for browsing and exporting assets from the mobile game *Choices: Stories You Play*. Point it at your local DLC cache folder to preview characters, custom items, spritesheets, CCBI scenes, and chapter stories as a branching dialog graph.

## Features

- **Characters** - browse character portraits with emotion variants and save individual emotions as PNG
- **Custom** - build and preview custom character outfits by mixing and matching slots (hair, hat, eyes, mouth, body, etc.)
- **Spritesheets** - view and play back animated spritesheets frame by frame with adjustable FPS
- **Scenes** - preview CCBI scene files with animated particle effects
- **Books** - explore chapter stories as an interactive branching dialog graph parsed directly from `.protobin` files
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
- [Claude](https://claude.ai)
- [Kimi](https://github.com/moonshot-ai) (Books tab / branching story graph, parser improvements, UI polish)
