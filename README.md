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

Choices Viewer is a desktop tool for browsing, previewing, and exporting assets from a local *Choices: Stories You Play* DLC cache.

Point it at the `dlc_cache` folder and it can display character portraits, custom outfit layers, animated CCBI scenes, loading screens, particle effects, book cover art, and chapter story data.

## What It Does

### Characters

- Browse character portraits from the DLC cache.
- Search by character name.
- Filter characters by the book they appear in.
- Preview emotion variants.
- Save character art as PNG, JPEG, or layered PSD.

### Custom

- Build custom character outfits from body, face, hair, clothing, accessories, props, tattoos, and other layers.
- Preview the current build live.
- Switch between supported emotions.
- Export custom builds as PNG, JPEG, or layered PSD.

### Scenes

- Browse CCBI scene files from the DLC cache.
- Filter scenes by book.
- Search scene names.
- Preview animated scene sequences, loading screens, overlays, backgrounds, and particle effects.
- Switch between available CCBI sequences.
- Export scene animations as PNG sequences, GIFs, or layered PSD files.

### Books

- Browse books with store-card cover art when available.
- Filter books by genre.
- Search book titles.
- Open chapters from `.protobin` files.
- View readable story flow with dialog and choices.

### General

- First-launch DLC folder picker.
- Saved DLC folder path for later launches.
- Folder switching from inside the app.
- Parallel asset discovery and cached indexes for faster loading.
- HiDPI-aware PyQt interface.
- Dark desktop theme.

## Requirements

- Python 3.10+
- A local *Choices* DLC cache folder

## Setup

```bash
pip install -r requirements.txt
```

## Running

Run from the parent directory of the `choices_viewer` folder:

```bash
python -m choices_viewer
```

On first launch, choose your DLC cache folder. The app expects the folder that contains the cache assets and books, usually named `dlc_cache`.

## Building

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name choices-viewer choices_viewer/__main__.py
```

The executable will be created in the `dist` folder.

## Credits

Written by sadblisscreations

- [Claude](https://claude.ai)
- [Kimi](https://kimi.com)
- [ChatGPT Codex](https://chatgpt.com)
