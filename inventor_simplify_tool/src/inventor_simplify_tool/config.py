"""Load and save STEP Simplify tool preferences as JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from inventor_utils.config import get_config_path, load_dataclass_config, save_dataclass_config


@dataclass
class SimplifyConfig:
    """User-configurable settings for the STEP Import + Simplify tool."""

    simplify_settings: dict[str, Any] = field(default_factory=dict)
    """Serialized SimplifySettings fields. Keys match SimplifySettings dataclass field names."""

    target_assembly_path: str = ""
    """Path to an already-open assembly to add simplified parts to."""

    add_to_assembly: bool = False
    """Whether to insert each simplified .ipt into the target assembly."""


def load_simplify_config(path: Path | None = None) -> SimplifyConfig:
    """Load SimplifyConfig from JSON file. Returns defaults if missing or corrupt."""
    if path is None:
        path = get_config_path("simplify_config.json")
    return load_dataclass_config(SimplifyConfig, path)


def save_simplify_config(config: SimplifyConfig, path: Path | None = None) -> None:
    """Save SimplifyConfig to JSON file."""
    if path is None:
        path = get_config_path("simplify_config.json")
    save_dataclass_config(config, path)
