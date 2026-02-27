"""Structured creation log for drawing creation and revision operations."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from inventor_utils.base_logger import ToolLogger
from inventor_utils.error_hints import error_hint

if TYPE_CHECKING:
    from inventor_drawing_tool.config import DrawingConfig
    from inventor_drawing_tool.models import (
        CreationItemResult,
        CreationSummary,
        RevisionData,
        ScanResult,
    )

_SEPARATOR = "=" * 60
_THIN_SEPARATOR = "-" * 60


class CreationLogger(ToolLogger):
    """Structured log file for drawing creation operations."""

    def __init__(self, output_folder: str | Path) -> None:
        super().__init__(output_folder, prefix="creation_log")

    def log_start(
        self,
        scan_result: "ScanResult",
        revision_data: "RevisionData",
        config: "DrawingConfig",
    ) -> None:
        """Log the creation configuration, scan results, and revision data."""
        self._write(_SEPARATOR)
        self._write("INVENTOR DRAWING CREATION LOG")
        self._write(_SEPARATOR)
        self._write(f"Date:     {datetime.datetime.now().isoformat()}")
        self._write(f"Assembly: {scan_result.assembly_path}")
        self._write("")

        self._write("REVISION DATA")
        self._write(f"  Rev Number:   {revision_data.rev_number or '(not set)'}")
        self._write(f"  Description:  {revision_data.rev_description or '(not set)'}")
        self._write(f"  Made By:      {revision_data.made_by or '(not set)'}")
        self._write(f"  Approved By:  {revision_data.approved_by or '(not set)'}")
        self._write("")

        self._write("SETTINGS")
        self._write(f"  Template:             {config.template_path or '(not set)'}")
        self._write(f"  Auto-create drawings: {config.auto_create_drawings}")
        self._write(f"  Include parts:        {config.include_parts}")
        self._write(f"  Include subassemblies:{config.include_subassemblies}")
        self._write(f"  Include suppressed:   {config.include_suppressed}")
        if config.max_depth is not None:
            self._write(f"  Max depth:            {config.max_depth}")
        self._write(f"  Save after revision:  {config.save_after_revision}")
        self._write(f"  Close after process:  {config.close_after_processing}")
        self._write("")

        self._write("SCAN RESULTS")
        self._write(f"  Total components:     {scan_result.total_parts}")
        self._write(f"  With drawings:        {scan_result.parts_with_drawings}")
        self._write(f"  Without drawings:     {scan_result.parts_without_drawings}")
        if scan_result.content_center_excluded:
            self._write(f"  Content Center excl.: {scan_result.content_center_excluded}")
        if scan_result.warnings:
            self._write("  Warnings:")
            for w in scan_result.warnings:
                self._write(f"    - {w}")
        self._write(_SEPARATOR)
        self._write("")
        self._write("PROCESSING")
        self._write(_THIN_SEPARATOR)

    def log_item(self, result: "CreationItemResult") -> None:
        """Log the result of processing one drawing."""
        status = "OK" if result.success else "FAILED"
        self._write(f"[{status}] {result.item.part_name:40s} ({result.duration_seconds:.1f}s)")
        self._write(f"         Part:    {result.item.part_path}")
        if result.item.drawing_path:
            self._write(f"         Drawing: {result.item.drawing_path}")
        self._write(f"         Action:  {result.action}")
        if result.error_message:
            self._write(f"         Error:   {result.error_message}")
            self._write(f"         Hint:    {error_hint(result.error_message)}")
        self._write("")

    def log_finish(self, summary: "CreationSummary") -> None:
        """Log the final summary with failed item details."""
        total_time = sum(r.duration_seconds for r in summary.results)

        self._write(_SEPARATOR)
        self._write("SUMMARY")
        self._write(_SEPARATOR)
        self._write(f"Finished:  {datetime.datetime.now().isoformat()}")
        self._write(
            f"Created: {summary.created}, Revised: {summary.revised}, "
            f"Failed: {summary.failed}, Total time: {total_time:.1f}s"
        )

        if summary.failed:
            self._write("")
            self._write("FAILED ITEMS")
            fail_num = 0
            for r in summary.results:
                if not r.success:
                    fail_num += 1
                    self._write(f"  {fail_num}. {r.item.part_name}")
                    self._write(f"     Part:    {r.item.part_path}")
                    if r.item.drawing_path:
                        self._write(f"     Drawing: {r.item.drawing_path}")
                    self._write(f"     Error:   {r.error_message}")
                    self._write(f"     Hint:    {error_hint(r.error_message or '')}")

        self._write("")
        self._write(_SEPARATOR)


__all__ = ["CreationLogger"]
