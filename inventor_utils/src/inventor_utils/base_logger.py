"""Abstract base class for structured tool log files."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO


class ToolLogger(ABC):
    """Base class for structured tool log files.

    Subclasses must implement log_start and log_finish.
    """

    def __init__(self, output_folder: str | Path, prefix: str) -> None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = Path(output_folder) / f"{prefix}_{timestamp}.txt"
        self._file: IO[str] | None = None

    @property
    def log_path(self) -> Path | None:
        return self._path

    def open(self) -> None:
        self._file = open(self._path, "w", encoding="utf-8")

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def _write(self, line: str) -> None:
        if self._file is None:
            raise RuntimeError("Logger not opened. Call open() first.")
        self._file.write(line + "\n")
        self._file.flush()

    def _write_section(self, title: str) -> None:
        self._write("=" * 60)
        self._write(title)
        self._write("=" * 60)

    def _timestamp(self) -> str:
        return datetime.datetime.now().isoformat()

    @abstractmethod
    def log_start(self, *args: object, **kwargs: object) -> None:
        """Write the header/start section of the log."""

    @abstractmethod
    def log_finish(self, *args: object, **kwargs: object) -> None:
        """Write the summary/finish section of the log."""
