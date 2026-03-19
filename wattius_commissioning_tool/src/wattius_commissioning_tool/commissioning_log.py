from __future__ import annotations

import csv
import logging
import os
from dataclasses import asdict
from datetime import datetime

from wattius_commissioning_tool.models import BoardResult

logger = logging.getLogger("zabra.commissioning")


class CommissioningLogger:
    """Logs commissioning results to a per-session CSV file."""

    COLUMNS = [
        "serial_number",
        "can_node_id",
        "firmware_version",
        "config_crc",
        "status",
        "failure_step",
        "failure_reason",
        "started_at",
        "completed_at",
    ]

    def __init__(self, log_directory: str) -> None:
        """Store log directory path. Don't create anything yet."""
        self._log_directory = log_directory
        self._session_path: str | None = None

    def start_session(self) -> None:
        """Create a new CSV file with header row.

        Filename: commissioning_YYYYMMDD_HHMMSS.csv
        Creates log_directory if it doesn't exist.
        """
        os.makedirs(self._log_directory, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"commissioning_{timestamp}.csv"
        self._session_path = os.path.join(self._log_directory, filename)
        with open(self._session_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.COLUMNS)
        logger.info("Started commissioning session: %s", self._session_path)

    def log_board(self, result: BoardResult) -> None:
        """Append one row to the CSV file for a completed board."""
        if self._session_path is None:
            raise RuntimeError("No active session. Call start_session() first.")
        row_data = asdict(result)
        row = [row_data[col] for col in self.COLUMNS]
        with open(self._session_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
        logger.debug("Logged board %s: %s", result.serial_number, result.status)

    def end_session(self) -> str:
        """Return the file path of the current session log."""
        if self._session_path is None:
            raise RuntimeError("No active session. Call start_session() first.")
        path = self._session_path
        logger.info("Ended commissioning session: %s", path)
        return path

    @property
    def session_path(self) -> str | None:
        """Return current session file path, or None if no session active."""
        return self._session_path
