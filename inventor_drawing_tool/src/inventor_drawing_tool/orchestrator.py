"""Orchestrator for batch drawing creation."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING

from inventor_api import InventorApp
from inventor_api.drawing import DrawingDocument, RevisionRowData
from inventor_api.exceptions import DrawingError
from inventor_utils.base_orchestrator import BaseOrchestrator, LogCallback, ProgressCallback

from inventor_drawing_tool.creation_log import CreationLogger
from inventor_drawing_tool.models import (
    DrawingItem,
    DrawingStatus,
    CreationItemResult,
    CreationSummary,
    RevisionData,
    ScanResult,
)
from inventor_drawing_tool.scanner import scan_assembly_for_creation

if TYPE_CHECKING:
    from inventor_drawing_tool.config import DrawingConfig

logger = logging.getLogger("zabra.drawing")


class DrawingCreationOrchestrator(BaseOrchestrator):
    """Orchestrates drawing creation and revision table writing.

    Two-phase operation:
    - scan(): Discover parts and their drawing status
    - execute(): Create missing drawings and write revision data

    Must be called from a thread with COM initialized (com_thread_scope).
    """

    def __init__(
        self,
        config: "DrawingConfig",
        revision_data: RevisionData,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        super().__init__(progress_callback, log_callback)
        self._config = config
        self._revision_data = revision_data
        self._app: InventorApp | None = None
        self._creation_logger: CreationLogger | None = None

    def scan(self) -> ScanResult:
        """Connect to Inventor and scan the active assembly.

        Returns:
            ScanResult with list of DrawingItems.
        """
        self._emit("Connecting to Inventor...")
        self._app = InventorApp.connect()
        self._emit("Scanning assembly tree...")
        result = scan_assembly_for_creation(self._app, self._config)
        self._emit(
            f"Found {result.total_parts} components: "
            f"{result.parts_with_drawings} with drawings, "
            f"{result.parts_without_drawings} without"
        )
        for warning in result.warnings:
            self._emit(f"Warning: {warning}")
        return result

    def execute(
        self,
        items: list[DrawingItem],
        cancel_event: Event | None = None,
    ) -> CreationSummary:
        """Execute the creation batch.

        For each selected item:
        1. If NEEDS_CREATION and config.auto_create_drawings:
           create drawing from template, insert views, save co-located
        2. Open drawing, add revision row, save, close

        Args:
            items: List of DrawingItems (pre-filtered by user selection).
            cancel_event: Optional event to signal cancellation.

        Returns:
            CreationSummary with per-item results.
        """
        if self._app is None:
            self._emit("Connecting to Inventor...")
            self._app = InventorApp.connect()

        selected = [i for i in items if i.include]
        total = len(selected)
        results: list[CreationItemResult] = []
        created = 0
        revised = 0
        failed = 0

        # Set up creation logger next to the first item's part file
        output_folder = os.path.dirname(items[0].part_path) if items else os.getcwd()
        self._creation_logger = CreationLogger(output_folder)

        try:
            self._creation_logger.open()
        except Exception as e:
            self._emit(f"WARNING: Could not create creation log: {e}")
            self._creation_logger = None

        scan_for_log = ScanResult(
            assembly_path=items[0].part_path if items else "",
            items=selected,
            total_parts=total,
            parts_with_drawings=sum(
                1 for i in selected if i.drawing_status == DrawingStatus.EXISTING
            ),
            parts_without_drawings=sum(
                1 for i in selected if i.drawing_status == DrawingStatus.NEEDS_CREATION
            ),
        )

        if self._creation_logger:
            try:
                self._creation_logger.log_start(scan_for_log, self._revision_data, self._config)
            except Exception as e:
                self._emit(f"WARNING: Could not write creation log header: {e}")

        self._emit(f"Processing {total} drawings...")

        for idx, item in enumerate(selected):
            if cancel_event and cancel_event.is_set():
                self._emit("Cancelled by user.")
                break

            self._progress(idx, total)
            start_time = time.monotonic()

            try:
                action = self._process_item(item)
                duration = time.monotonic() - start_time
                result = CreationItemResult(
                    item=item,
                    success=True,
                    action=action,
                    duration_seconds=duration,
                )
                if "created" in action:
                    created += 1
                if "revision" in action:
                    revised += 1
                self._emit(f"  OK: {item.part_name} ({action})")
            except Exception as e:
                duration = time.monotonic() - start_time
                failed += 1
                error_msg = str(e)
                result = CreationItemResult(
                    item=item,
                    success=False,
                    action="failed",
                    error_message=error_msg,
                    duration_seconds=duration,
                )
                self._emit(f"  FAIL: {item.part_name}: {error_msg}")
                logger.exception("Failed to process %s", item.part_name)

            results.append(result)
            if self._creation_logger:
                try:
                    self._creation_logger.log_item(result)
                except Exception as e:
                    self._emit(f"WARNING: Could not write to creation log: {e}")
                    self._creation_logger = None

        self._progress(total, total)

        summary = CreationSummary(
            total=total,
            created=created,
            revised=revised,
            failed=failed,
            results=results,
        )

        if self._creation_logger:
            try:
                self._creation_logger.log_finish(summary)
                self._creation_logger.close()
                self._emit(f"Log written to {self._creation_logger.log_path}")
            except Exception as e:
                self._emit(f"WARNING: Could not finalize creation log: {e}")

        self._emit(f"Complete: {created} created, {revised} revised, {failed} failed")
        return summary

    @property
    def last_log_path(self) -> Path | None:
        """Return the path to the last creation log file."""
        if self._creation_logger:
            return self._creation_logger.log_path
        return None

    def _process_item(self, item: DrawingItem) -> str:
        """Process a single drawing item. Returns action string."""
        assert self._app is not None

        drawing_path = item.drawing_path

        # Phase 1: Create drawing if needed
        if item.drawing_status == DrawingStatus.NEEDS_CREATION:
            if not self._config.auto_create_drawings:
                return "skipped"
            if not self._config.template_path:
                raise DrawingError(
                    item.part_path,
                    cause=RuntimeError("No drawing template configured"),
                )
            drawing_path = self._create_drawing(item)
            item.drawing_path = drawing_path
            item.drawing_status = DrawingStatus.EXISTING
            # Phase 2 also runs below — track that we created it
            self._write_revision(drawing_path)
            return "created+revision"

        # Phase 2: Write revision data to existing drawing
        if drawing_path is None:
            return "skipped"

        self._write_revision(drawing_path)
        return "revision_only"

    def _create_drawing(self, item: DrawingItem) -> str:
        """Create a new drawing from template with standard views.

        Returns the path to the new drawing file.
        """
        assert self._app is not None

        self._emit(f"  Creating drawing for {item.part_name}...")

        drawing = self._app.create_drawing(self._config.template_path)

        # Open the part/assembly document for view insertion
        model_doc = self._app.open_document(item.part_path, visible=False)

        try:
            base_view = None
            if self._config.insert_base_view:
                base_view = drawing.insert_base_view(
                    model_doc.com_object,
                    x=self._config.base_view_x,
                    y=self._config.base_view_y,
                    scale=self._config.default_scale,
                )

            if self._config.insert_top_view and base_view is not None:
                drawing.insert_projected_view(
                    base_view,
                    x=self._config.base_view_x,
                    y=self._config.base_view_y + self._config.top_view_offset_y,
                )

            if self._config.insert_right_view and base_view is not None:
                drawing.insert_projected_view(
                    base_view,
                    x=self._config.base_view_x + self._config.right_view_offset_x,
                    y=self._config.base_view_y,
                )

            if self._config.insert_iso_view and base_view is not None:
                drawing.insert_projected_view(
                    base_view,
                    x=self._config.iso_view_x,
                    y=self._config.iso_view_y,
                )
        except Exception:
            # Views are best-effort; log but don't fail the whole item
            logger.warning("View insertion failed for %s", item.part_name)

        # Save co-located with the part file
        part_dir = os.path.dirname(item.part_path)
        part_stem = os.path.splitext(os.path.basename(item.part_path))[0]
        drawing_path = os.path.join(part_dir, f"{part_stem}.idw")

        drawing.save_as(drawing_path)
        if self._config.close_after_processing:
            drawing.close()

        return drawing_path

    def _write_revision(self, drawing_path: str) -> None:
        """Open a drawing, add revision row, save, close."""
        assert self._app is not None

        doc = self._app.open_document(drawing_path, visible=False)
        if not isinstance(doc, DrawingDocument):
            drawing_doc = DrawingDocument(doc.com_object)
        else:
            drawing_doc = doc

        rev_data = RevisionRowData(
            rev_number=self._revision_data.rev_number,
            rev_description=self._revision_data.rev_description,
            made_by=self._revision_data.made_by,
            approved_by=self._revision_data.approved_by,
        )

        drawing_doc.add_revision_row(rev_data)

        if self._config.save_after_revision:
            drawing_doc.save()

        if self._config.close_after_processing:
            drawing_doc.close()


__all__ = ["DrawingCreationOrchestrator"]
