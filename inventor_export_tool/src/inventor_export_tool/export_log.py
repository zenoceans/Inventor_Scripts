"""Structured export logging to file."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from inventor_utils.base_logger import ToolLogger
from inventor_utils.error_hints import error_hint

if TYPE_CHECKING:
    from inventor_export_tool.config import AppConfig
    from inventor_export_tool.models import ExportResult, ScanSummary

_SEPARATOR = "=" * 60
_THIN_SEPARATOR = "-" * 60


def _format_options(options: dict[str, object]) -> str:
    """Format an options dict as 'Key=Value, Key2=Value2'."""
    if not options:
        return "(Inventor defaults)"
    return ", ".join(f"{k}={v}" for k, v in options.items())


class ExportLogger(ToolLogger):
    """Writes a structured log file during export."""

    def __init__(self, output_folder: str | Path) -> None:
        super().__init__(output_folder, prefix="export_log")

    def log_config(
        self,
        config: AppConfig,
        assembly_name: str,
        assembly_path: str,
    ) -> None:
        """Write the header block with config, settings, and export options."""
        self._write(_SEPARATOR)
        self._write("INVENTOR EXPORT LOG")
        self._write(_SEPARATOR)
        self._write(f"Date:     {self._timestamp()}")
        self._write(f"Assembly: {assembly_name}")
        self._write(f"Path:     {assembly_path}")
        self._write(f"Output:   {config.output_folder}")
        self._write("")

        # Settings
        formats = []
        if config.export_step:
            formats.append("STEP")
        if config.export_dwg:
            formats.append("DWG")
        if config.export_pdf:
            formats.append("PDF")
        self._write("SETTINGS")
        self._write(f"  Formats: {', '.join(formats) or 'none'}")

        included = []
        if config.include_parts:
            included.append("parts")
        if config.include_subassemblies:
            included.append("sub-assemblies")
        if config.include_top_level:
            included.append("top-level assembly")
        self._write(f"  Include: {', '.join(included) or 'none'}")

        excluded = []
        if not config.include_suppressed:
            excluded.append("suppressed components")
        excluded.append("Content Center parts")
        self._write(f"  Exclude: {', '.join(excluded)}")
        self._write("")

        # Export options
        self._write("EXPORT OPTIONS")
        opts = config.export_options
        self._write(f"  STEP: {_format_options(opts.get('step', {}))}")
        self._write(f"  PDF:  {_format_options(opts.get('pdf', {}))}")
        self._write(f"  DWG:  {_format_options(opts.get('dwg', {}))}")
        self._write("")

    def log_start(self, summary: ScanSummary) -> None:
        """Write the scan results section."""
        self._write("SCAN RESULTS")
        self._write(f"  Components found:        {summary.total_components}")
        self._write(f"  Content Center excluded: {summary.content_center_excluded}")
        self._write(f"  Suppressed excluded:     {summary.suppressed_excluded}")
        self._write(f"  Files to export:         {len(summary.export_items)}")
        if summary.warnings:
            self._write("  Warnings:")
            for w in summary.warnings:
                self._write(f"    - {w}")
        self._write(_SEPARATOR)
        self._write("")
        self._write("EXPORT")
        self._write(_THIN_SEPARATOR)

    def log_export(self, result: ExportResult) -> None:
        """Write the result of a single export item."""
        status = "OK" if result.success else "FAILED"
        self._write(
            f"[{status}] {result.item.output_filename:40s} ({result.duration_seconds:.1f}s)"
        )

        # Source file
        self._write(f"         Source: {result.item.component.source_path}")

        # IDW path for drawing exports
        if result.item.export_type in ("dwg", "pdf") and result.item.component.idw_path:
            self._write(f"         Drawing: {result.item.component.idw_path}")

        # Error details with actionable hint
        if result.error_message:
            self._write(f"         Error: {result.error_message}")
            self._write(f"         Hint:  {error_hint(result.error_message)}")

        self._write("")

    def log_finish(self, results: list[ExportResult]) -> None:
        """Write the summary section with failed item details."""
        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        total_time = sum(r.duration_seconds for r in results)

        self._write(_SEPARATOR)
        self._write("SUMMARY")
        self._write(_SEPARATOR)
        self._write(f"Finished:  {self._timestamp()}")
        self._write(f"Succeeded: {succeeded}, Failed: {failed}, Total time: {total_time:.1f}s")

        if failed:
            self._write("")
            self._write("FAILED ITEMS")
            fail_num = 0
            for r in results:
                if not r.success:
                    fail_num += 1
                    self._write(f"  {fail_num}. {r.item.output_filename}")
                    self._write(f"     Source:  {r.item.component.source_path}")
                    if r.item.component.idw_path:
                        self._write(f"     Drawing: {r.item.component.idw_path}")
                    self._write(f"     Error:   {r.error_message}")
                    self._write(f"     Hint:    {error_hint(r.error_message or '')}")

        self._write("")
        self._write("To change export settings, edit config.json next to the tool executable.")
        self._write('See README.md "Export Options" for all available translator options.')
        self._write(_SEPARATOR)
