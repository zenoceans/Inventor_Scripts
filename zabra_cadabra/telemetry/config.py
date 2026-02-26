"""Load and save telemetry preferences as JSON."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path


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
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return TelemetryConfig()
        valid_fields = {f.name for f in fields(TelemetryConfig)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return TelemetryConfig(**filtered)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return TelemetryConfig()


def save_telemetry_config(config: TelemetryConfig, path: Path | None = None) -> None:
    """Save telemetry config to JSON file."""
    if path is None:
        path = get_telemetry_config_path()
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
