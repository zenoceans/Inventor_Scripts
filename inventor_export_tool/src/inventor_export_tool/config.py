"""Load and save user preferences as JSON."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


@dataclass
class AppConfig:
    """User-configurable settings persisted between sessions."""

    output_folder: str = ""
    export_step: bool = True
    export_dwg: bool = True
    export_pdf: bool = True
    include_parts: bool = True
    include_subassemblies: bool = True
    include_top_level: bool = True
    include_suppressed: bool = False
    export_options: dict[str, dict[str, Any]] = field(default_factory=dict)


def get_config_path() -> Path:
    """Return path to config.json next to the main script/executable."""
    if getattr(sys, "frozen", False):
        # PyInstaller executable
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from JSON file. Returns defaults if missing or corrupt."""
    if path is None:
        path = get_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return AppConfig()
        # Only accept known fields
        valid_fields = {f.name for f in fields(AppConfig)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return AppConfig(**filtered)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return AppConfig()


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Save config to JSON file."""
    if path is None:
        path = get_config_path()
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
