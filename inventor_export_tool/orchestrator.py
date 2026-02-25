"""Orchestrates scan and export operations."""

from __future__ import annotations

import os
import time
from pathlib import Path
from threading import Event
from typing import Callable

from inventor_api import InventorApp, InventorDocument
from inventor_api.exceptions import ExportError, InventorError
from inventor_api.exporters import export_drawing, export_step
from inventor_api.traversal import DiscoveredComponent, walk_assembly
from inventor_api.types import DocumentType

from inventor_export_tool.config import AppConfig
from inventor_export_tool.export_log import ExportLogger
from inventor_export_tool.models import ComponentInfo, ExportItem, ExportResult, ScanSummary
from inventor_export_tool.naming import (
    compose_filename,
    find_idw_path,
    resolve_duplicates,
)


def _to_component_info(comp: DiscoveredComponent) -> ComponentInfo:
    """Convert an inventor_api DiscoveredComponent to an app-level ComponentInfo."""
    doc = comp.document
    doc_type = "assembly" if doc.document_type == DocumentType.ASSEMBLY else "part"
    idw = find_idw_path(doc.full_path)
    return ComponentInfo(
        source_path=doc.full_path,
        display_name=doc.display_name,
        document_type=doc_type,
        revision=doc.get_revision(),
        is_top_level=comp.is_top_level,
        idw_path=idw,
        is_content_center=doc.is_content_center,
        is_suppressed=comp.is_suppressed,
    )


def _build_export_items(
    components: list[ComponentInfo],
    config: AppConfig,
    output_folder: str,
) -> list[ExportItem]:
    """Build the list of ExportItems based on config settings."""
    items: list[ExportItem] = []

    for comp in components:
        # Filter by component type
        if comp.is_top_level and not config.include_top_level:
            continue
        if (
            comp.document_type == "assembly"
            and not comp.is_top_level
            and not config.include_subassemblies
        ):
            continue
        if comp.document_type == "part" and not config.include_parts:
            continue

        # STEP export
        if config.export_step:
            filename = compose_filename(comp.display_name, comp.revision, "step")
            items.append(
                ExportItem(
                    component=comp,
                    export_type="step",
                    output_filename=filename,
                    output_path=os.path.join(output_folder, filename),
                )
            )

        # DWG/PDF from IDW
        if comp.idw_path:
            if config.export_dwg:
                filename = compose_filename(comp.display_name, comp.revision, "dwg")
                items.append(
                    ExportItem(
                        component=comp,
                        export_type="dwg",
                        output_filename=filename,
                        output_path=os.path.join(output_folder, filename),
                    )
                )
            if config.export_pdf:
                filename = compose_filename(comp.display_name, comp.revision, "pdf")
                items.append(
                    ExportItem(
                        component=comp,
                        export_type="pdf",
                        output_filename=filename,
                        output_path=os.path.join(output_folder, filename),
                    )
                )

    return items


ProgressCallback = Callable[[int, int], None]
LogCallback = Callable[[str], None]


class ExportOrchestrator:
    """Orchestrates scan and export operations.

    Designed to run on a background thread. Uses COM thread scope internally.

    Args:
        config: Application configuration.
        progress_callback: Called with (current, total) during export.
        log_callback: Called with status messages for display.
    """

    def __init__(
        self,
        config: AppConfig,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        self._config = config
        self._progress = progress_callback or (lambda c, t: None)
        self._log = log_callback or (lambda m: None)
        self._app: InventorApp | None = None
        self._doc_cache: dict[str, InventorDocument] = {}
        self._assembly_name: str = ""
        self._assembly_path: str = ""
        self._last_log_path: Path | None = None

    def _emit(self, msg: str) -> None:
        self._log(msg)

    def scan(self) -> ScanSummary:
        """Connect to Inventor, walk the assembly tree, and build an export plan.

        Must be called from a thread with COM initialized (use com_thread_scope).
        """
        self._emit("Connecting to Inventor...")
        self._app = InventorApp.connect()

        self._emit("Getting active assembly...")
        assembly = self._app.get_active_assembly()
        self._assembly_name = assembly.display_name
        self._assembly_path = assembly.full_path
        self._emit(f"Assembly: {self._assembly_name}")

        self._emit("Scanning assembly tree...")
        discovered = walk_assembly(
            assembly,
            include_suppressed=self._config.include_suppressed,
        )

        # Count excluded items
        all_count = len(discovered)
        content_center_count = sum(1 for c in discovered if c.document.is_content_center)
        suppressed_count = 0  # Already filtered by walk_assembly unless included

        # Cache document references so export can reuse them (avoids re-opening
        # files by path, which would trigger Vault checkout dialogs).
        self._doc_cache = {c.document.full_path: c.document for c in discovered}

        # Convert to ComponentInfo
        components = [_to_component_info(c) for c in discovered]
        self._emit(
            f"Found {len(components)} components ({content_center_count} Content Center excluded)"
        )

        # Build export items
        items = _build_export_items(components, self._config, self._config.output_folder)

        # Resolve duplicate filenames
        warnings: list[str] = []
        original_names = [item.output_filename for item in items]
        resolve_duplicates(items)
        for i, item in enumerate(items):
            if item.output_filename != original_names[i]:
                warnings.append(
                    f"Renamed {original_names[i]} -> {item.output_filename} (duplicate)"
                )

        summary = ScanSummary(
            total_components=all_count,
            content_center_excluded=content_center_count,
            suppressed_excluded=suppressed_count,
            export_items=items,
            warnings=warnings,
        )

        self._emit(f"Export plan: {len(items)} files to export")
        for item in items:
            idw_note = ""
            if item.export_type in ("dwg", "pdf"):
                idw_note = " (from IDW)"
            self._emit(f"  {item.output_filename} [{item.export_type.upper()}]{idw_note}")

        return summary

    def export(
        self,
        summary: ScanSummary,
        cancel_event: Event | None = None,
    ) -> list[ExportResult]:
        """Execute the export plan.

        Must be called after scan() on the same thread (same COM connection).

        Args:
            summary: The scan summary containing items to export.
            cancel_event: Set this event to cancel between files.

        Returns:
            List of ExportResult for each item.
        """
        if self._app is None:
            raise InventorError("Must call scan() before export()")

        results: list[ExportResult] = []
        total = len(summary.export_items)

        # Set up logger
        logger: ExportLogger | None = None
        if self._config.output_folder:
            try:
                os.makedirs(self._config.output_folder, exist_ok=True)
                logger = ExportLogger(self._config.output_folder)
                logger.open()
                logger.log_config(self._config, self._assembly_name, self._assembly_path)
                logger.log_start(summary)
            except Exception as e:
                self._emit(f"WARNING: Could not create export log: {e}")
                logger = None

        self._emit(f"Starting export of {total} files...")

        for i, item in enumerate(summary.export_items):
            if cancel_event and cancel_event.is_set():
                self._emit("Export cancelled by user.")
                break

            self._progress(i, total)
            self._emit(f"Exporting {item.output_filename}...")

            start_time = time.monotonic()
            try:
                self._export_item(item)
                duration = time.monotonic() - start_time
                result = ExportResult(item=item, success=True, duration_seconds=duration)
                self._emit(f"  OK ({duration:.1f}s)")
            except Exception as e:
                duration = time.monotonic() - start_time
                result = ExportResult(
                    item=item,
                    success=False,
                    error_message=str(e),
                    duration_seconds=duration,
                )
                self._emit(f"  FAILED: {e}")

            results.append(result)
            if logger:
                try:
                    logger.log_export(result)
                except Exception as e:
                    self._emit(f"WARNING: Could not write to export log: {e}")
                    logger = None  # Stop trying to write to broken log

        self._progress(total, total)

        # Final summary
        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        self._emit(f"Export complete: {succeeded} succeeded, {failed} failed")

        if logger:
            try:
                logger.log_finish(results)
                logger.close()
                self._last_log_path = logger.log_path
                self._emit(f"Log written to {logger.log_path}")
            except Exception as e:
                self._emit(f"WARNING: Could not finalize export log: {e}")

        return results

    @property
    def last_log_path(self) -> Path | None:
        return self._last_log_path

    def _export_item(self, item: ExportItem) -> None:
        """Export a single item. Raises on failure."""
        assert self._app is not None

        if item.export_type == "step":
            # Reuse the document reference from scan — avoids re-opening by path,
            # which would trigger Vault checkout dialogs.
            try:
                doc = self._doc_cache[item.component.source_path]
            except KeyError:
                raise ExportError(
                    path=item.component.source_path,
                    format="step",
                    cause=RuntimeError(
                        "Document not found in memory. "
                        "The file may have been closed or moved between scan and export. "
                        "Try scanning again."
                    ),
                )
            export_step(
                self._app,
                doc,
                item.output_path,
                options=self._config.export_options.get("step"),
            )

        elif item.export_type in ("dwg", "pdf"):
            if item.component.idw_path is None:
                raise ExportError(
                    path=item.component.source_path,
                    format=item.export_type,
                    cause=RuntimeError("No IDW file found"),
                )
            export_drawing(
                self._app,
                item.component.idw_path,
                item.output_path,
                item.export_type,
                options=self._config.export_options.get(item.export_type),
            )


__all__ = ["ExportOrchestrator"]
