"""Configuration for the drawing creation tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from inventor_utils.config import (
    get_config_path,
    load_dataclass_config,
    save_dataclass_config,
)

_CONFIG_FILENAME = "drawing_config.json"


@dataclass
class DrawingConfig:
    """User-configurable settings for the drawing creation tool."""

    # Drawing template
    template_path: str = ""

    # Scan settings
    include_parts: bool = True
    include_subassemblies: bool = False
    include_suppressed: bool = False
    include_content_center: bool = False
    max_depth: int | None = None  # None=unlimited, 1=top-level, 2=two levels...

    # Drawing creation settings
    auto_create_drawings: bool = True
    default_scale: float = 1.0
    insert_base_view: bool = True
    insert_top_view: bool = True
    insert_right_view: bool = False
    insert_iso_view: bool = True
    base_view_x: float = 15.0
    base_view_y: float = 15.0
    top_view_offset_y: float = 12.0
    right_view_offset_x: float = 15.0
    iso_view_x: float = 32.0
    iso_view_y: float = 25.0

    # Revision settings (remembered from last use)
    last_rev_number: str = ""
    last_rev_description: str = ""
    last_made_by: str = ""
    last_approved_by: str = ""

    # Advanced
    save_after_revision: bool = True
    close_after_processing: bool = True


def get_drawing_config_path() -> Path:
    """Return the path to the drawing config file."""
    return get_config_path(_CONFIG_FILENAME)


def load_drawing_config(path: Path | None = None) -> DrawingConfig:
    """Load drawing config from JSON, returning defaults on error."""
    if path is None:
        path = get_drawing_config_path()
    return load_dataclass_config(DrawingConfig, path)


def save_drawing_config(config: DrawingConfig, path: Path | None = None) -> None:
    """Save drawing config to JSON."""
    if path is None:
        path = get_drawing_config_path()
    save_dataclass_config(config, path)
