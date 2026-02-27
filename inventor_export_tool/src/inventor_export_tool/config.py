"""Load and save user preferences as JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from inventor_utils.config import get_config_path, load_dataclass_config, save_dataclass_config


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


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from JSON file. Returns defaults if missing or corrupt."""
    if path is None:
        path = get_config_path("config.json")
    return load_dataclass_config(AppConfig, path)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Save config to JSON file."""
    if path is None:
        path = get_config_path("config.json")
    save_dataclass_config(config, path)
