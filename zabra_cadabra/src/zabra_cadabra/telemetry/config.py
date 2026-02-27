"""Load and save telemetry preferences as JSON."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from inventor_utils.config import load_dataclass_config, save_dataclass_config


@dataclass
class TelemetryConfig:
    """User-configurable telemetry settings persisted between sessions."""

    enabled: bool = True
    network_path: str = ""
    network_sync_enabled: bool = False
    log_level: str = "INFO"
    auto_popup_on_error: bool = True
    include_username: bool = False


def get_telemetry_config_path() -> Path:
    """Return path to telemetry_config.json next to the main script/executable."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "telemetry_config.json"


def load_telemetry_config(path: Path | None = None) -> TelemetryConfig:
    """Load telemetry config from JSON file. Returns defaults if missing or corrupt."""
    if path is None:
        path = get_telemetry_config_path()
    return load_dataclass_config(TelemetryConfig, path)


def save_telemetry_config(config: TelemetryConfig, path: Path | None = None) -> None:
    """Save telemetry config to JSON file."""
    if path is None:
        path = get_telemetry_config_path()
    save_dataclass_config(config, path)
