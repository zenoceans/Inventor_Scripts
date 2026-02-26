"""Structured export logging to file."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from inventor_export_tool.config import AppConfig
    from inventor_export_tool.models import ExportResult, ScanSummary

_SEPARATOR = "=" * 60
_THIN_SEPARATOR = "-" * 60


def _error_hint(error_message: str) -> str:
    """Return an actionable hint based on the error message pattern."""
    msg = error_message.lower()
    if "failed to open document" in msg or "could not open" in msg:
        return (
            "Check that the file exists, is not open in another program, "
            "and is not checked out in Vault by another user."
        )
    if "no idw file found" in msg or "idw" in msg and "not found" in msg:
        return (
            "DWG/PDF export requires an IDW drawing file with the same name "
            "as the part/assembly, in the same folder."
        )
    if "translator" in msg:
        return (
            "The required Inventor translator add-in could not be found. "
            "Check that Inventor is installed correctly."
        )
    if "not found in memory" in msg or "document not found" in msg:
        return (
            "The document may have been closed or moved between scan and export. "
            "Try scanning again."
        )
    return (
        "Check that Inventor is running, the document is accessible, and try again. "
        "If the problem persists, share this log file for troubleshooting."
    )


def _format_options(options: dict[str, object]) -> str:
    """Format an options dict as 'Key=Value, Key2=Value2'."""
    if not options:
        return "(Inventor defaults)"
    return ", ".join(f"{k}={v}" for k, v in options.items())


class ExportLogger:
    """Writes a structured log file during export."""

    def __init__(self, output_folder: str | Path) -> None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = Path(output_folder) / f"export_log_{timestamp}.txt"
        self._file: IO[str] | None = None

    @property
    def log_path(self) -> Path:
        return self._path

    def open(self) -> None:
        self._file = open(self._path, "w", encoding="utf-8")

    def _write(self, text: str) -> None:
        if self._file is None:
            raise RuntimeError("Logger not opened. Call open() first.")
        self._file.write(text + "\n")
        self._file.flush()

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
        self._write(f"Date:     {datetime.datetime.now().isoformat()}")
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
            self._write(f"         Hint:  {_error_hint(result.error_message)}")

        self._write("")

    def log_finish(self, results: list[ExportResult]) -> None:
        """Write the summary section with failed item details."""
        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        total_time = sum(r.duration_seconds for r in results)

        self._write(_SEPARATOR)
        self._write("SUMMARY")
        self._write(_SEPARATOR)
        self._write(f"Finished:  {datetime.datetime.now().isoformat()}")
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
                    self._write(f"     Hint:    {_error_hint(r.error_message or '')}")

        self._write("")
        self._write("To change export settings, edit config.json next to the tool executable.")
        self._write('See README.md "Export Options" for all available translator options.')
        self._write(_SEPARATOR)

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
