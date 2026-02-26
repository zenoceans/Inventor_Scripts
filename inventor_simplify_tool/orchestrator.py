"""Orchestrate batch STEP Import + Simplify operations."""

from __future__ import annotations

import dataclasses
import logging
import os
import time
from pathlib import Path
from threading import Event
from typing import Callable

from inventor_api.application import InventorApp
from inventor_api.importer import import_step, is_assembly_document
from inventor_api.simplifier import SimplifySettings, simplify_document

from inventor_simplify_tool.config import SimplifyConfig
from inventor_simplify_tool.models import SimplifyResult, SimplifyRow, SimplifySummary
from inventor_simplify_tool.simplify_log import SimplifyLogger

_log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]
LogCallback = Callable[[str], None]


class SimplifyOrchestrator:
    """Batch STEP import + simplify.  Designed to run on a background thread."""

    def __init__(
        self,
        config: SimplifyConfig,
        rows: list[SimplifyRow],
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        self._config = config
        self._rows = rows
        self._progress = progress_callback or (lambda c, t: None)
        self._log_cb = log_callback or (lambda m: None)
        self._app: InventorApp | None = None
        self._last_log_path: Path | None = None

    @property
    def last_log_path(self) -> Path | None:
        return self._last_log_path

    def _emit(self, msg: str) -> None:
        _log.info(msg)
        self._log_cb(msg)

    def run(self, cancel_event: Event | None = None) -> SimplifySummary:
        """Connect to Inventor and process all rows.

        Must be called inside a ``com_thread_scope`` if on a background thread.
        """
        self._emit("Connecting to Inventor...")
        self._app = InventorApp.connect()

        settings = self._build_settings()
        results: list[SimplifyResult] = []
        total = len(self._rows)

        # Set up logger in the first row's output folder (or CWD)
        log_folder = self._rows[0].output_folder if self._rows else os.getcwd()
        logger = self._open_logger(log_folder, total)

        for i, row in enumerate(self._rows):
            if cancel_event and cancel_event.is_set():
                self._emit("Cancelled by user.")
                break

            self._progress(i, total)
            self._emit(f"Processing ({i + 1}/{total}): {row.step_path}")

            start = time.monotonic()
            result = self._process_row(row, settings)
            result.duration_seconds = time.monotonic() - start
            results.append(result)

            if result.success:
                self._emit(f"  OK ({result.duration_seconds:.1f}s) -> {result.output_path}")
                _log.info(
                    "simplify_item",
                    extra={
                        "data": {
                            "file": row.step_path,
                            "success": True,
                            "duration": round(result.duration_seconds, 2),
                        }
                    },
                )
            else:
                self._emit(f"  FAILED: {result.error_message}")
                _log.info(
                    "simplify_item",
                    extra={
                        "data": {
                            "file": row.step_path,
                            "success": False,
                            "error": result.error_message,
                        }
                    },
                )

            if logger:
                try:
                    logger.log_result(result)
                except Exception:
                    pass

        self._progress(total, total)
        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded

        summary = SimplifySummary(
            total_rows=total,
            succeeded=succeeded,
            failed=failed,
            results=results,
        )

        self._emit(f"Done: {succeeded} succeeded, {failed} failed.")
        total_time = sum(r.duration_seconds for r in results)
        _log.info(
            "simplify_batch",
            extra={
                "data": {
                    "succeeded": succeeded,
                    "failed": failed,
                    "total_time": round(total_time, 2),
                }
            },
        )
        self._close_logger(logger, summary)
        return summary

    def _build_settings(self) -> SimplifySettings:
        """Construct SimplifySettings from the config dict."""
        d = self._config.simplify_settings
        valid = {f.name for f in dataclasses.fields(SimplifySettings)}
        return SimplifySettings(**{k: v for k, v in d.items() if k in valid})

    def _process_row(self, row: SimplifyRow, settings: SimplifySettings) -> SimplifyResult:
        """Import and simplify a single STEP file."""
        assert self._app is not None
        output_filename = row.output_filename
        if not output_filename.lower().endswith(".ipt"):
            output_filename += ".ipt"
        output_path = os.path.join(row.output_folder, output_filename)

        imported_as_assembly = False
        try:
            doc = import_step(self._app, row.step_path, visible=True)
            imported_as_assembly = is_assembly_document(doc)
            result_doc = simplify_document(self._app, doc, output_path, settings)

            # Optionally add to target assembly
            if self._config.add_to_assembly and self._config.target_assembly_path:
                self._add_to_assembly(result_doc.full_path)

            return SimplifyResult(
                row=row,
                success=True,
                output_path=result_doc.full_path,
                imported_as_assembly=imported_as_assembly,
            )
        except Exception as e:
            return SimplifyResult(
                row=row,
                success=False,
                imported_as_assembly=imported_as_assembly,
                error_message=str(e),
            )

    def _add_to_assembly(self, ipt_path: str) -> None:
        """Insert the simplified .ipt into the target assembly at origin.

        The target assembly must already be open in Inventor.
        """
        assert self._app is not None
        target = self._config.target_assembly_path
        try:
            # Find the already-open target assembly
            target_doc = None
            for doc in self._app.com_app.Documents:
                if doc.FullFileName.lower() == target.lower():
                    target_doc = doc
                    break
            if target_doc is None:
                self._emit(f"  WARNING: Target assembly not open: {target}")
                return

            comp_def = target_doc.ComponentDefinition
            matrix = self._app.com_app.TransientGeometry.CreateMatrix()
            comp_def.Occurrences.Add(ipt_path, matrix)
            self._emit(f"  Added to assembly: {target}")
        except Exception as e:
            self._emit(f"  WARNING: Could not add to assembly: {e}")

    def _open_logger(self, log_folder: str, total: int) -> SimplifyLogger | None:
        """Create and open the log file."""
        try:
            os.makedirs(log_folder, exist_ok=True)
            logger = SimplifyLogger(log_folder)
            logger.open()
            logger.log_start(self._config, total)
            return logger
        except Exception as e:
            self._emit(f"WARNING: Could not create simplify log: {e}")
            return None

    def _close_logger(self, logger: SimplifyLogger | None, summary: SimplifySummary) -> None:
        """Finalize and close the log file."""
        if not logger:
            return
        try:
            logger.log_finish(summary)
            logger.close()
            self._last_log_path = logger.log_path
            self._emit(f"Log: {logger.log_path}")
        except Exception as e:
            self._emit(f"WARNING: Could not finalize log: {e}")


__all__ = ["SimplifyOrchestrator"]
