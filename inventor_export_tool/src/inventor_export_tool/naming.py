"""Filename composition, IDW finding, and duplicate resolution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from inventor_utils.filenames import (
    compose_filename,
    find_idw_path,
    is_content_center_path,
    sanitize_filename,
)

if TYPE_CHECKING:
    from inventor_export_tool.models import ExportItem

__all__ = [
    "compose_filename",
    "find_idw_path",
    "is_content_center_path",
    "resolve_duplicates",
    "sanitize_filename",
]


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
