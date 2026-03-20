"""Load and save PDF Diff tool preferences as JSON."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from inventor_utils.config import get_config_path, load_dataclass_config, save_dataclass_config


@dataclass
class PdfDiffConfig:
    """User-configurable settings for the PDF Diff tool."""

    dpi: int = 150
    open_after_diff: bool = True
    last_old_path: str = ""
    last_new_path: str = ""


def load_config(path: Path | None = None) -> PdfDiffConfig:
    """Load PdfDiffConfig from JSON file. Returns defaults if missing or corrupt."""
    if path is None:
        path = get_config_path("pdf_diff_config.json")
    return load_dataclass_config(PdfDiffConfig, path)


def save_config(config: PdfDiffConfig, path: Path | None = None) -> None:
    """Save PdfDiffConfig to JSON file."""
    if path is None:
        path = get_config_path("pdf_diff_config.json")
    save_dataclass_config(config, path)
