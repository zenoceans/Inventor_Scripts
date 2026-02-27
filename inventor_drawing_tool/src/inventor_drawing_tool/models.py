"""Data models for the drawing creation tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DrawingStatus(str, Enum):
    """Status of a drawing relative to its part."""

    EXISTING = "existing"
    NEEDS_CREATION = "new"


@dataclass
class DrawingItem:
    """One part/assembly and its associated drawing for the creation batch."""

    part_path: str
    part_name: str
    drawing_path: str | None
    drawing_status: DrawingStatus
    document_type: str  # "part" or "assembly"
    depth: int
    include: bool = True


@dataclass
class RevisionData:
    """Revision fields entered once, applied to all drawings."""

    rev_number: str = ""
    rev_description: str = ""
    made_by: str = ""
    approved_by: str = ""


@dataclass
class ScanResult:
    """Result of scanning an assembly for drawing creation candidates."""

    assembly_path: str
    items: list[DrawingItem] = field(default_factory=list)
    total_parts: int = 0
    parts_with_drawings: int = 0
    parts_without_drawings: int = 0
    content_center_excluded: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class CreationItemResult:
    """Result of processing one drawing."""

    item: DrawingItem
    success: bool
    action: str = ""  # "created+revision", "revision_only", "skipped"
    error_message: str | None = None
    duration_seconds: float = 0.0


@dataclass
class CreationSummary:
    """Summary of the complete creation batch."""

    total: int = 0
    created: int = 0
    revised: int = 0
    failed: int = 0
    results: list[CreationItemResult] = field(default_factory=list)
