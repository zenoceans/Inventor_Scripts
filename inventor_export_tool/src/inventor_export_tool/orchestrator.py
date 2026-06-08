"""Orchestrates scan and export operations."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from threading import Event

from inventor_api import InventorApp, InventorDocument
from inventor_api._vault_dialog_suppressor import vault_dialog_suppressor
from inventor_api.document import AssemblyDocument
from inventor_api.exceptions import ExportError, InventorError
from inventor_api.exporters import export_drawing, export_step
from inventor_api.traversal import DiscoveredComponent, walk_assembly
from inventor_api.types import DocumentType

from inventor_export_tool.config import AppConfig
from inventor_export_tool.export_log import ExportLogger
from inventor_export_tool.models import ComponentInfo, ExportItem, ExportResult, ScanSummary
from inventor_export_tool.naming import (
    find_idw_path,
    resolve_duplicates,
    sanitize_filename,
)
from inventor_export_tool.templates import render_template
from inventor_utils.base_orchestrator import BaseOrchestrator, LogCallback, ProgressCallback

_tel = logging.getLogger("zabra.export")


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


def _normalize_prefixes(prefixes: list[str]) -> list[str]:
    """Strip whitespace and drop empty entries; lowercase for case-insensitive match."""
    return [p.strip().lower() for p in prefixes if p and p.strip()]


def _matches_excluded_prefix(display_name: str, normalized_prefixes: list[str]) -> bool:
    """True if display_name starts with any of the (already-normalized) prefixes."""
    if not normalized_prefixes:
        return False
    name_lower = display_name.lower()
    return any(name_lower.startswith(p) for p in normalized_prefixes)


def _build_export_items(
    components: list[ComponentInfo],
    config: AppConfig,
    output_folder: str,
    doc_cache: dict[str, "InventorDocument"],
    single_part: bool = False,
) -> list[ExportItem]:
    """Build the list of ExportItems based on config and active naming preset."""
    preset = config.active_preset()
    items: list[ExportItem] = []
    excluded_prefixes = _normalize_prefixes(config.excluded_filename_prefixes)

    for comp in components:
        if not single_part:
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
            if _matches_excluded_prefix(comp.display_name, excluded_prefixes):
                continue

        # Render base name once per component
        doc = doc_cache.get(comp.source_path)
        if doc is not None:
            base_name = render_template(preset.template, doc, fallback_filename=comp.display_name)
        else:
            base_name = sanitize_filename(comp.display_name)

        if config.export_step:
            filename = f"{base_name}.step"
            items.append(
                ExportItem(
                    component=comp,
                    export_type="step",
                    output_filename=filename,
                    output_path=os.path.join(output_folder, filename),
                )
            )

        if comp.idw_path:
            if config.export_dwg:
                filename = f"{base_name}.dwg"
                items.append(
                    ExportItem(
                        component=comp,
                        export_type="dwg",
                        output_filename=filename,
                        output_path=os.path.join(output_folder, filename),
                    )
                )
            if config.export_pdf:
                filename = f"{base_name}.pdf"
                items.append(
                    ExportItem(
                        component=comp,
                        export_type="pdf",
                        output_filename=filename,
                        output_path=os.path.join(output_folder, filename),
                    )
                )

    return items


class ExportOrchestrator(BaseOrchestrator):
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
        super().__init__(progress_callback, log_callback)
        self._config = config
        self._app: InventorApp | None = None
        self._doc_cache: dict[str, InventorDocument] = {}
        self._assembly_name: str = ""
        self._assembly_path: str = ""
        self._last_log_path: Path | None = None

    def _emit(self, msg: str) -> None:
        _tel.info(msg)
        self._log_cb(msg)

    def scan(self, output_folder: str | None = None) -> ScanSummary:
        """Connect to Inventor, walk the assembly tree, and build an export plan.

        Args:
            output_folder: Override the config output folder for naming/path generation.
                           If None, uses self._config.output_folder.

        Must be called from a thread with COM initialized (use com_thread_scope).
        """
        with vault_dialog_suppressor(on_dismiss=self._emit):
            return self._scan_impl(output_folder)

    def _scan_impl(self, output_folder: str | None) -> ScanSummary:
        self._emit("Connecting to Inventor...")
        self._app = InventorApp.connect()

        self._emit("Getting active assembly or part...")
        doc = self._app.get_active_part_or_assembly()
        self._assembly_name = doc.display_name
        self._assembly_path = doc.full_path
        self._emit(f"Document: {self._assembly_name}")

        self._emit("Scanning document...")
        if isinstance(doc, AssemblyDocument):
            discovered = walk_assembly(
                doc,
                include_suppressed=self._config.include_suppressed,
            )
            single_part = False
        else:
            discovered = [DiscoveredComponent(document=doc, is_top_level=True, depth=0)]
            single_part = True

        # Count excluded items
        all_count = len(discovered)
        content_center_count = sum(1 for c in discovered if c.document.is_content_center)
        suppressed_count = 0  # Already filtered by walk_assembly unless included

        # Cache document references so export can reuse them (avoids re-opening
        # files by path, which would trigger Vault checkout dialogs).
        self._doc_cache = {c.document.full_path: c.document for c in discovered}

        # Convert to ComponentInfo
        components = [_to_component_info(c) for c in discovered]

        # Count prefix-excluded for reporting (filter is applied in _build_export_items).
        normalized_prefixes = _normalize_prefixes(self._config.excluded_filename_prefixes)
        prefix_excluded_count = sum(
            1 for c in components if _matches_excluded_prefix(c.display_name, normalized_prefixes)
        )

        prefix_note = (
            f", {prefix_excluded_count} excluded by prefix" if normalized_prefixes else ""
        )
        self._emit(
            f"Found {len(components)} components "
            f"({content_center_count} Content Center excluded{prefix_note})"
        )

        # Build export items
        effective_folder = (
            output_folder if output_folder is not None else self._config.output_folder
        )
        items = _build_export_items(
            components, self._config, effective_folder, self._doc_cache, single_part=single_part
        )

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
            prefix_excluded=prefix_excluded_count,
            export_items=items,
            warnings=warnings,
        )

        self._emit(f"Export plan: {len(items)} files to export")
        _tel.info(
            "scan_finish",
            extra={
                "data": {
                    "components": all_count,
                    "export_items": len(items),
                    "content_center_excluded": content_center_count,
                    "prefix_excluded": prefix_excluded_count,
                }
            },
        )
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

        with vault_dialog_suppressor(on_dismiss=self._emit):
            return self._export_impl(summary, cancel_event)

    def _export_impl(
        self,
        summary: ScanSummary,
        cancel_event: Event | None,
    ) -> list[ExportResult]:
        assert self._app is not None
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
                _tel.info(
                    "export_item",
                    extra={
                        "data": {
                            "file": item.output_filename,
                            "format": item.export_type,
                            "success": True,
                            "duration": round(duration, 2),
                        }
                    },
                )
            except Exception as e:
                duration = time.monotonic() - start_time
                result = ExportResult(
                    item=item,
                    success=False,
                    error_message=str(e),
                    duration_seconds=duration,
                )
                self._emit(f"  FAILED: {e}")
                _tel.info(
                    "export_item",
                    extra={
                        "data": {
                            "file": item.output_filename,
                            "format": item.export_type,
                            "success": False,
                            "duration": round(duration, 2),
                            "error": str(e),
                        }
                    },
                )

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
        total_time = sum(r.duration_seconds for r in results)
        _tel.info(
            "export_batch",
            extra={
                "data": {
                    "succeeded": succeeded,
                    "failed": failed,
                    "total_time": round(total_time, 2),
                }
            },
        )

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
