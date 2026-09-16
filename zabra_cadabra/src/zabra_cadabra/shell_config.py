"""Load and save shell-level preferences (hidden tabs) as JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from inventor_utils.config import get_config_path, load_dataclass_config, save_dataclass_config


@dataclass
class ShellConfig:
    """Tab titles the user has chosen to hide from the notebook."""

    hidden_tabs: list[str] = field(default_factory=list)


def load_shell_config(path: Path | None = None) -> ShellConfig:
    """Load ShellConfig from JSON file. Returns defaults if missing or corrupt."""
    if path is None:
        path = get_config_path("zabra_cadabra_shell_config.json")
    return load_dataclass_config(ShellConfig, path)


def save_shell_config(config: ShellConfig, path: Path | None = None) -> None:
    """Save ShellConfig to JSON file."""
    if path is None:
        path = get_config_path("zabra_cadabra_shell_config.json")
    save_dataclass_config(config, path)
