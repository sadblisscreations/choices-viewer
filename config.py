import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".choices_viewer.json"


def resource_path(name: str) -> Path:
    """Return the absolute path to a bundled resource.
    When frozen by PyInstaller the files live in sys._MEIPASS; otherwise
    they sit next to the package root."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    return base / name


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def save_config(data: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        pass
