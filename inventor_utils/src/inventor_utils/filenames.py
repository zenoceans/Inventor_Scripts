"""Filename sanitization and IDW-finding utilities."""

from __future__ import annotations

import os
import re

# Characters invalid in Windows filenames
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Remove or replace characters invalid in Windows filenames."""
    sanitized = _INVALID_CHARS.sub("_", name)
    # Strip trailing dots and spaces (Windows restriction)
    sanitized = sanitized.rstrip(". ")
    return sanitized if sanitized else "_"


def find_idw_path(source_path: str) -> str | None:
    """Find the co-located .idw file for an .ipt or .iam file.

    Returns the IDW path if it exists, None otherwise.
    Checks both .idw and .IDW (case-insensitive on Windows, but explicit).
    """
    base = os.path.splitext(source_path)[0]
    idw_path = base + ".idw"
    if os.path.exists(idw_path):
        return idw_path
    idw_path_upper = base + ".IDW"
    if os.path.exists(idw_path_upper):
        return idw_path_upper
    return None


def is_content_center_path(file_path: str) -> bool:
    """Check if a file path is from Inventor's Content Center."""
    return "content center files" in file_path.lower()
