"""Install global exception hooks that route unhandled errors to the feedback dialog."""

from __future__ import annotations

import logging
import sys
import traceback
import tkinter as tk
from typing import Any, Callable

_logger = logging.getLogger("zabra.error")


def install_error_hooks(
    root: tk.Tk,
    feedback_opener: Callable[[dict[str, Any] | None], None],
) -> None:
    """Override sys.excepthook and root.report_callback_exception to capture errors.

    Args:
        root: The Tk root window. Used to schedule callbacks on the main thread.
        feedback_opener: Callable that opens the feedback dialog, receiving an
            error_context dict (or None). Called on the main thread.
    """

    def _excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: object,
    ) -> None:
        _logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_tb),  # type: ignore[arg-type]
        )
        error_context: dict[str, Any] = {
            "type": exc_type.__name__,
            "message": str(exc_value),
            "traceback": "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)  # type: ignore[arg-type]
            ),
        }
        root.after(0, feedback_opener, error_context)

    sys.excepthook = _excepthook

    def _report_callback_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: object,
    ) -> None:
        _logger.critical(
            "Unhandled Tk callback exception",
            exc_info=(exc_type, exc_value, exc_tb),  # type: ignore[arg-type]
        )
        error_context: dict[str, Any] = {
            "type": exc_type.__name__,
            "message": str(exc_value),
            "traceback": "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)  # type: ignore[arg-type]
            ),
        }
        feedback_opener(error_context)

    root.report_callback_exception = _report_callback_exception  # type: ignore[method-assign]
