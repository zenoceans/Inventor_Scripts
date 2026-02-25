"""Custom exception hierarchy for the Inventor API wrapper."""

from __future__ import annotations

import re


def _format_cause(cause: Exception) -> str:
    """Extract a human-readable message from an exception.

    COM errors from pywin32 look like::

        (-2147352567, 'Exception occurred.', (0, 'Inventor', 'desc', '', 0, -21474), None)

    This extracts the description field when possible.
    """
    text = str(cause)
    # pywintypes.com_error tuple: try to find a readable description inside
    match = re.search(r"\(\d+,\s*'[^']*',\s*\(\d+,\s*'[^']*',\s*'([^']+)'", text)
    if match:
        return match.group(1)
    # Strip the class name prefix if it's just wrapping another exception
    if text.startswith("(-"):
        # Raw COM tuple — return a generic message
        return f"COM error: {text}"
    return text


class InventorError(Exception):
    """Base exception for all Inventor API errors."""


class InventorNotRunningError(InventorError):
    """Inventor application is not running or not reachable via COM."""


class InventorNotAssemblyError(InventorError):
    """Active document is not an assembly."""


class DocumentOpenError(InventorError):
    """Failed to open an Inventor document."""

    def __init__(self, path: str, cause: Exception | None = None) -> None:
        self.path = path
        self.cause = cause
        msg = f"Failed to open document: {path}"
        if cause:
            msg += f" ({_format_cause(cause)})"
        super().__init__(msg)


class ExportError(InventorError):
    """Failed to export a document."""

    def __init__(self, path: str, format: str, cause: Exception | None = None) -> None:
        self.path = path
        self.format = format
        self.cause = cause
        msg = f"Failed to export {path} as {format}"
        if cause:
            msg += f" ({_format_cause(cause)})"
        super().__init__(msg)


class TranslatorError(ExportError):
    """Translator add-in not found or not available."""
