"""Data models for PDF diff results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiffResult:
    """Result of comparing two PDFs."""

    output_path: Path
    page_count: int
    has_differences: bool
