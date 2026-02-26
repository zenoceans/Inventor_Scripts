"""Data models for the export tool."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ComponentInfo:
    """A discovered component in the assembly tree."""

    source_path: str
    display_name: str
    document_type: str  # "part" | "assembly"
    revision: str  # "NoRev" if empty
    is_top_level: bool = False
    idw_path: str | None = None
    is_content_center: bool = False
    is_suppressed: bool = False


@dataclass
class ExportItem:
    """A single file to be exported."""

    component: ComponentInfo
    export_type: str  # "step" | "dwg" | "pdf"
    output_filename: str
    output_path: str


@dataclass
class ExportResult:
    """Result of exporting one item."""

    item: ExportItem
    success: bool
    error_message: str | None = None
    duration_seconds: float = 0.0


@dataclass
class ScanSummary:
    """Summary of a dry-run scan."""

    total_components: int
    content_center_excluded: int
    suppressed_excluded: int
    export_items: list[ExportItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
