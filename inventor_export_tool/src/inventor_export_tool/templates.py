"""Token-based filename template engine for the export tool."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from inventor_utils.filenames import sanitize_filename

if TYPE_CHECKING:
    from inventor_api.document import InventorDocument

BUILTIN_TOKENS: list[str] = [
    "filename",
    "Part Number",
    "Description",
    "Project",
    "Revision Number",
    "Title",
    "Subject",
    "Author",
    "Comments",
    "Category",
    "Company",
    "Manager",
    "Material",
    "Cost Center",
    "Checked By",
    "Engineer Approved By",
]

_TOKEN_RE = re.compile(r"\{([^{}]+)\}")


def render_template(template: str, doc: "InventorDocument", fallback_filename: str) -> str:
    """Render ``template`` against ``doc``'s iProperties.

    Tokens are ``{Property Name}`` (case-insensitive, spaces allowed).
    Special token ``{filename}`` resolves to the file stem of ``doc.full_path``.
    Missing or None values render as empty string.

    Post-processing (applied to the final rendered string):
    1. Sanitize for Windows filenames.
    2. Collapse runs of whitespace to a single space and strip.
    3. Strip leading/trailing dashes and spaces.
    4. If the result is empty, return ``fallback_filename``.
    """
    file_stem = os.path.splitext(os.path.basename(doc.full_path))[0]

    def _resolve(token: str) -> str:
        if token.lower() == "filename":
            return file_stem
        value = doc.get_iproperty(token)
        return value if value is not None else ""

    result = _TOKEN_RE.sub(lambda m: _resolve(m.group(1)), template)
    result = re.sub(r"\s+", " ", result).strip()
    result = result.strip(" -")
    if not result:
        return fallback_filename
    result = sanitize_filename(result)
    return result if result else fallback_filename
