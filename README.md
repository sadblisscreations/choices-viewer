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

A desktop tool for browsing and exporting assets from the mobile game *Choices: Stories You Play*. Point it at your local DLC cache folder to preview characters, build custom outfits, play back animated spritesheets and CCBI scenes, and explore chapter stories as a branching dialog graph.

## Features

### Characters
- Browse every character portrait found in the DLC cache
- Search by name and filter by source book (each portrait is matched to the books that reference it via the chapter `.protobin` asset manifest, so you see exactly which characters, NPCs and animals belong to each story)
- View all five emotion variants per character (Neutral, Happy, Angry, Sad, Surprised)
- Save a single emotion, the full character, or every character in the DLC cache as **PNG**, **JPEG**, or layered **PSD**

### Custom Builder
- Mix and match 13 outfit slots: body, face, hair (front/back), clothing, hat (front/back), prop (front/back), scarf/strap, accessory (front/back), tattoo
- Live preview with debounced re-render as you change layers
- Switch between all five emotions for the current build
- Save the current build, or every emotion of the current build, as **PNG**, **JPEG**, or layered **PSD** (one group per emotion)
- Works with both custom-builder items and non-custom portrait sets, mixed freely

### Spritesheets
- List and search every effect spritesheet in the DLC cache
- Frame-by-frame playback with adjustable FPS (6 – 24) and a scrubber slider
- First / previous / play / next / last transport controls
- CCBI-aware depth-layer detection so spritesheets that tile spatial layers (rather than animating temporally) render correctly as static composites
- Save a single frame as **PNG**, **GIF**, or **PSD**, or save every frame as a sequence of PNGs, an animated **GIF** at the chosen FPS, or a single layered **PSD** with one frame per group

### Scenes
- Render CCBI scene files with animated particle effects (fire, smoke, sparkles, etc.) over the original background
- Cached, tinted texture atlas for fast emitter rendering
- Scene navigation, restart button, and live emitter / particle / sequence-name readout
- Search and filter the scene list

### Books
- Explore every chapter `.protobin` as an interactive branching dialog graph
- Dialog blocks, choice forks, and chapter breaks are colour-coded and connected with flow lines
- Speaker names and emotion tags shown alongside each line
- Heuristic protobuf decoder works with or without `google.protobuf` installed

### General
- First-launch folder picker with live DLC validation; change folder later without restarting
- Parallel asset discovery with persistent on-disk cache for near-instant subsequent launches
- Loading screen with per-stage progress
- HiDPI / 4K aware
- Dark Windows-98-style theme

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
