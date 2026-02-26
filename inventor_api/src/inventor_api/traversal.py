"""Assembly tree traversal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from inventor_api.document import AssemblyDocument, InventorDocument

if TYPE_CHECKING:
    pass


@dataclass
class DiscoveredComponent:
    """A component found during assembly traversal.

    Attributes:
        document: The wrapped Inventor document.
        is_top_level: True for the root assembly itself.
        is_suppressed: True if the occurrence was suppressed.
    """

    document: InventorDocument
    is_top_level: bool = False
    is_suppressed: bool = False


def walk_assembly(
    assembly: AssemblyDocument,
    *,
    include_suppressed: bool = False,
    include_content_center: bool = False,
) -> list[DiscoveredComponent]:
    """Recursively walk an assembly tree and return discovered components.

    The assembly itself is included as a top-level component.
    Duplicate documents (same file path) are visited only once.

    Args:
        assembly: The root assembly to traverse.
        include_suppressed: If True, include suppressed occurrences.
        include_content_center: If True, include Content Center parts.

    Returns:
        List of DiscoveredComponent in traversal order.
    """
    visited: set[str] = set()
    result: list[DiscoveredComponent] = []

    # Include the top-level assembly itself
    top_path = assembly.full_path.lower()
    visited.add(top_path)
    result.append(DiscoveredComponent(document=assembly, is_top_level=True))

    _walk_recursive(assembly, visited, result, include_suppressed, include_content_center)
    return result


def _walk_recursive(
    assembly: AssemblyDocument,
    visited: set[str],
    result: list[DiscoveredComponent],
    include_suppressed: bool,
    include_content_center: bool,
) -> None:
    """Recursively walk occurrences, adding to result list."""
    for occ in assembly.occurrences:
        is_suppressed = occ.is_suppressed

        if is_suppressed and not include_suppressed:
            continue

        try:
            ref_doc = occ.referenced_document
        except Exception:
            continue  # Skip inaccessible occurrences

        path_key = ref_doc.full_path.lower()
        if path_key in visited:
            continue
        visited.add(path_key)

        if ref_doc.is_content_center and not include_content_center:
            continue

        result.append(
            DiscoveredComponent(
                document=ref_doc,
                is_suppressed=is_suppressed,
            )
        )

        # Recurse into sub-assemblies
        if isinstance(ref_doc, AssemblyDocument):
            _walk_recursive(ref_doc, visited, result, include_suppressed, include_content_center)
