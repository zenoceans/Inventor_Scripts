"""Filename composition, IDW finding, and duplicate resolution."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inventor_export_tool.models import ExportItem

# Characters invalid in Windows filenames
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Remove or replace characters invalid in Windows filenames."""
    sanitized = _INVALID_CHARS.sub("_", name)
    # Strip trailing dots and spaces (Windows restriction)
    sanitized = sanitized.rstrip(". ")
    return sanitized if sanitized else "_"


def compose_filename(display_name: str, revision: str, extension: str) -> str:
    """Compose export filename: 'Bracket', 'B', 'step' → 'Bracket-B.step'.

    Empty or whitespace-only revision becomes 'NoRev'.
    Extension should not include the dot.
    """
    rev = revision.strip() if revision else ""
    if not rev:
        rev = "NoRev"
    name = sanitize_filename(display_name)
    rev = sanitize_filename(rev)
    return f"{name}-{rev}.{extension}"


def find_idw_path(source_path: str) -> str | None:
    """Find the co-located .idw file for an .ipt or .iam file.

    Returns the IDW path if it exists, None otherwise.
    Checks both .idw and .IDW (case-insensitive on Windows, but explicit).
    """
    base = os.path.splitext(source_path)[0]
    idw_path = base + ".idw"
    if os.path.exists(idw_path):
        return idw_path
    # Try uppercase extension
    idw_path_upper = base + ".IDW"
    if os.path.exists(idw_path_upper):
        return idw_path_upper
    return None


def is_content_center_path(file_path: str) -> bool:
    """Check if a file path is from Inventor's Content Center."""
    return "content center files" in file_path.lower()


def resolve_duplicates(items: list[ExportItem]) -> list[ExportItem]:
    """Detect filename collisions and append _2, _3 suffixes.

    Modifies output_filename and output_path on colliding items.
    Returns the same list (mutated in place) for convenience.
    """
    seen: dict[str, int] = {}
    for item in items:
        key = item.output_filename.lower()
        if key in seen:
            seen[key] += 1
            count = seen[key]
            name, ext = os.path.splitext(item.output_filename)
            item.output_filename = f"{name}_{count}{ext}"
            # Update output_path to match
            folder = os.path.dirname(item.output_path)
            item.output_path = os.path.join(folder, item.output_filename)
        else:
            seen[key] = 1
    return items
