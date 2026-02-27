"""Data models for the drawing release tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DrawingStatus(str, Enum):
    """Status of a drawing relative to its part."""

    EXISTING = "existing"
    NEEDS_CREATION = "new"


@dataclass
class DrawingItem:
    """One part/assembly and its associated drawing for the release batch."""

    part_path: str
    part_name: str
    drawing_path: str | None
    drawing_status: DrawingStatus
    document_type: str  # "part" or "assembly"
    depth: int
    include_in_release: bool = True


@dataclass
class RevisionData:
    """Revision fields entered once, applied to all drawings."""

    rev_number: str = ""
    rev_description: str = ""
    made_by: str = ""
    approved_by: str = ""


@dataclass
class ScanResult:
    """Result of scanning an assembly for drawing release candidates."""

    assembly_path: str
    items: list[DrawingItem] = field(default_factory=list)
    total_parts: int = 0
    parts_with_drawings: int = 0
    parts_without_drawings: int = 0
    content_center_excluded: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReleaseItemResult:
    """Result of processing one drawing in the release."""

    item: DrawingItem
    success: bool
    action: str = ""  # "created+revision", "revision_only", "skipped"
    error_message: str | None = None
    duration_seconds: float = 0.0


@dataclass
class ReleaseSummary:
    """Summary of the complete release batch."""

    total: int = 0
    created: int = 0
    revised: int = 0
    failed: int = 0
    results: list[ReleaseItemResult] = field(default_factory=list)
