"""Generic config helpers for dataclass-based JSON persistence."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def get_config_path(filename: str) -> Path:
    """Return a PyInstaller-aware path for a config file next to the executable/script."""
    if getattr(sys, "frozen", False):
        # PyInstaller executable
        base = Path(sys.executable).parent
    else:
        # Development: two levels up from the calling module (package root)
        base = Path(__file__).resolve().parent.parent.parent.parent
    return base / filename


def load_dataclass_config(cls: type[T], path: Path) -> T:
    """Load a dataclass from a JSON file. Returns defaults if missing or corrupt.

    Unknown JSON keys are silently ignored. Missing keys use dataclass defaults.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return cls()  # type: ignore[call-arg]
        valid_fields = {f.name for f in fields(cls)}  # type: ignore[arg-type]
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)  # type: ignore[call-arg]
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return cls()  # type: ignore[call-arg]


def save_dataclass_config(config: Any, path: Path) -> None:
    """Save a dataclass instance to a JSON file."""
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
