"""Base class for tool orchestrators with progress and log callbacks."""

from __future__ import annotations

from typing import Callable

ProgressCallback = Callable[[int, int], None]  # (current, total)
LogCallback = Callable[[str], None]  # (message)


class BaseOrchestrator:
    """Base class for tool orchestrators with progress and log callbacks."""

    def __init__(
        self,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        self._progress_cb = progress_callback or (lambda c, t: None)
        self._log_cb = log_callback or (lambda m: None)

    def _emit(self, msg: str) -> None:
        self._log_cb(msg)

    def _progress(self, current: int, total: int) -> None:
        self._progress_cb(current, total)
