"""Load and save STEP Simplify tool preferences as JSON."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


@dataclass
class SimplifyConfig:
    """User-configurable settings for the STEP Import + Simplify tool."""

    simplify_settings: dict[str, Any] = field(default_factory=dict)
    """Serialized SimplifySettings fields. Keys match SimplifySettings dataclass field names."""

    target_assembly_path: str = ""
    """Path to an already-open assembly to add simplified parts to."""

    add_to_assembly: bool = False
    """Whether to insert each simplified .ipt into the target assembly."""


def get_simplify_config_path() -> Path:
    """Return path to simplify_config.json next to the main script/executable."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "simplify_config.json"


def load_simplify_config(path: Path | None = None) -> SimplifyConfig:
    """Load SimplifyConfig from JSON file. Returns defaults if missing or corrupt."""
    if path is None:
        path = get_simplify_config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return SimplifyConfig()
        valid_fields = {f.name for f in fields(SimplifyConfig)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return SimplifyConfig(**filtered)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return SimplifyConfig()


def save_simplify_config(config: SimplifyConfig, path: Path | None = None) -> None:
    """Save SimplifyConfig to JSON file."""
    if path is None:
        path = get_simplify_config_path()
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
