"""Logging for STEP Import + Simplify operations."""

from __future__ import annotations

from pathlib import Path

from inventor_utils.base_logger import ToolLogger
from inventor_utils.error_hints import error_hint

from inventor_simplify_tool.models import SimplifyResult, SimplifySummary


class SimplifyLogger(ToolLogger):
    """Write a human-readable log file for a simplify batch run."""

    def __init__(self, output_folder: str | Path) -> None:
        super().__init__(output_folder, prefix="simplify_log")

    def log_start(self, config: object, total_rows: int) -> None:
        """Write the header section."""
        self._write("=" * 60)
        self._write("STEP Import + Simplify Log")
        self._write(f"Date: {self._timestamp()}")
        self._write(f"Total rows: {total_rows}")
        if hasattr(config, "add_to_assembly") and config.add_to_assembly:
            target = getattr(config, "target_assembly_path", "")
            self._write(f"Add to assembly: {target}")
        self._write("=" * 60)
        self._write("")

    def log_result(self, result: SimplifyResult) -> None:
        """Write one result entry."""
        status = "[OK]" if result.success else "[FAILED]"
        self._write(f"{status} {result.row.step_path}")
        if result.success:
            self._write(f"  Output: {result.output_path}")
            if result.imported_as_assembly:
                self._write("  Note: Imported as assembly, derived to .ipt")
        else:
            self._write(f"  Error: {result.error_message}")
            hint = error_hint(result.error_message or "")
            if hint:
                self._write(f"  Hint: {hint}")
        self._write(f"  Duration: {result.duration_seconds:.1f}s")
        self._write("")

    def log_finish(self, summary: SimplifySummary) -> None:
        """Write the summary footer."""
        self._write("=" * 60)
        self._write("Summary")
        self._write(f"  Total:     {summary.total_rows}")
        self._write(f"  Succeeded: {summary.succeeded}")
        self._write(f"  Failed:    {summary.failed}")
        if summary.failed > 0:
            self._write("")
            self._write("Failed items:")
            for r in summary.results:
                if not r.success:
                    self._write(f"  - {r.row.step_path}: {r.error_message}")
        self._write("=" * 60)
