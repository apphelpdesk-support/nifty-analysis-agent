"""Settings loader for the Nifty Analyst project."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "settings.json"


def load_settings(path=None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def rel(settings: dict, key: str) -> Path:
    """Resolve a path key from settings relative to the project root."""
    return ROOT / settings["paths"][key]