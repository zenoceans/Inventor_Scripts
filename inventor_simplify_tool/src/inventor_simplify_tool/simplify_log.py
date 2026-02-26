"""Logging for STEP Import + Simplify operations."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from inventor_simplify_tool.models import SimplifyResult, SimplifySummary


def _error_hint(error_message: str) -> str:
    """Return an actionable hint based on known error patterns."""
    lower = error_message.lower()
    if "file not found" in lower or "not found" in lower:
        return "Check that the STEP file exists and the path is correct."
    if "simplif" in lower:
        return "The Simplify feature failed. Verify Inventor 2026 is running and Simplify is available for this document type."
    if "save" in lower or "write" in lower:
        return "Check the output folder exists and you have write permissions."
    if "com error" in lower or "com_error" in lower or "rpc" in lower:
        return "COM communication error. Ensure Inventor is responsive and not showing a dialog."
    return ""


class SimplifyLogger:
    """Write a human-readable log file for a simplify batch run."""

    def __init__(self, output_folder: str | Path) -> None:
        output_folder = Path(output_folder)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = output_folder / f"simplify_log_{timestamp}.txt"
        self._file: io.TextIOWrapper | None = None

    @property
    def log_path(self) -> Path:
        return self._path

    def open(self) -> None:
        self._file = open(self._path, "w", encoding="utf-8")

    def _write(self, text: str) -> None:
        if self._file:
            self._file.write(text)
            self._file.flush()

    def log_start(self, config: Any, total_rows: int) -> None:
        """Write the header section."""
        self._write("=" * 60 + "\n")
        self._write("STEP Import + Simplify Log\n")
        self._write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._write(f"Total rows: {total_rows}\n")
        if hasattr(config, "add_to_assembly") and config.add_to_assembly:
            target = getattr(config, "target_assembly_path", "")
            self._write(f"Add to assembly: {target}\n")
        self._write("=" * 60 + "\n\n")

    def log_result(self, result: SimplifyResult) -> None:
        """Write one result entry."""
        status = "[OK]" if result.success else "[FAILED]"
        self._write(f"{status} {result.row.step_path}\n")
        if result.success:
            self._write(f"  Output: {result.output_path}\n")
            if result.imported_as_assembly:
                self._write("  Note: Imported as assembly, derived to .ipt\n")
        else:
            self._write(f"  Error: {result.error_message}\n")
            hint = _error_hint(result.error_message or "")
            if hint:
                self._write(f"  Hint: {hint}\n")
        self._write(f"  Duration: {result.duration_seconds:.1f}s\n")
        self._write("\n")

    def log_finish(self, summary: SimplifySummary) -> None:
        """Write the summary footer."""
        self._write("=" * 60 + "\n")
        self._write("Summary\n")
        self._write(f"  Total:     {summary.total_rows}\n")
        self._write(f"  Succeeded: {summary.succeeded}\n")
        self._write(f"  Failed:    {summary.failed}\n")
        if summary.failed > 0:
            self._write("\nFailed items:\n")
            for r in summary.results:
                if not r.success:
                    self._write(f"  - {r.row.step_path}: {r.error_message}\n")
        self._write("=" * 60 + "\n")

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None
