"""Assembly tree traversal."""

from __future__ import annotations

from dataclasses import dataclass, field
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
        depth: Nesting depth. 0 for the top-level assembly, 1 for direct children, etc.
    """

    document: InventorDocument
    is_top_level: bool = False
    is_suppressed: bool = False
    depth: int = field(default=0)


def walk_assembly(
    assembly: AssemblyDocument,
    *,
    include_suppressed: bool = False,
    include_content_center: bool = False,
    max_depth: int | None = None,
    include_parts: bool = True,
    include_assemblies: bool = True,
) -> list[DiscoveredComponent]:
    """Recursively walk an assembly tree and return discovered components.

    The assembly itself is included as a top-level component (unless
    ``include_assemblies=False``, in which case it is still the starting
    point but may not appear in the result list depending on how you use
    the flag — the root assembly is always included for consistency).

    Duplicate documents (same file path) are visited only once.

    Args:
        assembly: The root assembly to traverse.
        include_suppressed: If True, include suppressed occurrences.
        include_content_center: If True, include Content Center parts.
        max_depth: Maximum traversal depth relative to the root assembly.
            ``None`` means unlimited. ``1`` returns only direct children of
            the root assembly; ``2`` adds their children, and so on.
        include_parts: If True (default), include part documents (.ipt) in
            the result list.
        include_assemblies: If True (default), include sub-assembly documents
            (.iam) in the result list. Sub-assemblies are still *traversed*
            even when False so their child parts can be found.

    Returns:
        List of DiscoveredComponent in traversal order.
    """
    visited: set[str] = set()
    result: list[DiscoveredComponent] = []

    # Include the top-level assembly itself
    top_path = assembly.full_path.lower()
    visited.add(top_path)
    result.append(DiscoveredComponent(document=assembly, is_top_level=True, depth=0))

    _walk_recursive(
        assembly,
        visited,
        result,
        include_suppressed,
        include_content_center,
        current_depth=1,
        max_depth=max_depth,
        include_parts=include_parts,
        include_assemblies=include_assemblies,
    )
    return result


def _walk_recursive(
    assembly: AssemblyDocument,
    visited: set[str],
    result: list[DiscoveredComponent],
    include_suppressed: bool,
    include_content_center: bool,
    current_depth: int,
    max_depth: int | None,
    include_parts: bool,
    include_assemblies: bool,
) -> None:
    """Recursively walk occurrences, adding to result list."""
    if max_depth is not None and current_depth > max_depth:
        return
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

        is_assembly = isinstance(ref_doc, AssemblyDocument)
        is_part = not is_assembly

        # Add to results based on type filters
        if (is_part and include_parts) or (is_assembly and include_assemblies):
            result.append(
                DiscoveredComponent(
                    document=ref_doc,
                    is_suppressed=is_suppressed,
                    depth=current_depth,
                )
            )

        # Recurse into sub-assemblies (even if include_assemblies=False, to find child parts)
        if is_assembly and (max_depth is None or current_depth < max_depth):
            _walk_recursive(
                ref_doc,  # type: ignore[arg-type]
                visited,
                result,
                include_suppressed,
                include_content_center,
                current_depth=current_depth + 1,
                max_depth=max_depth,
                include_parts=include_parts,
                include_assemblies=include_assemblies,
            )
