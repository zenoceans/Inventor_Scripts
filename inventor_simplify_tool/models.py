"""Data models for the STEP Import + Simplify tool."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimplifyRow:
    """One user-supplied input row in the batch table."""

    step_path: str
    """Absolute path to the .stp / .step file."""

    output_filename: str
    """Desired output filename (without .ipt extension — appended automatically)."""

    output_folder: str
    """Destination folder for the simplified .ipt."""


@dataclass
class SimplifyResult:
    """Result of processing one SimplifyRow."""

    row: SimplifyRow
    success: bool
    output_path: str | None = None
    imported_as_assembly: bool = False
    error_message: str | None = None
    duration_seconds: float = 0.0


@dataclass
class SimplifySummary:
    """Summary of a completed batch simplify run."""

    total_rows: int
    succeeded: int
    failed: int
    results: list[SimplifyResult] = field(default_factory=list)
