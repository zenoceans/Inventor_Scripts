"""Scan assembly tree to find parts and their drawing status."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from inventor_api import AssemblyDocument, walk_assembly
from inventor_utils.filenames import find_idw_path

from inventor_drawing_tool.models import DrawingItem, DrawingStatus, ScanResult

if TYPE_CHECKING:
    from inventor_api import InventorApp

    from inventor_drawing_tool.config import DrawingConfig

logger = logging.getLogger("zabra.drawing")


def scan_assembly_for_release(
    app: "InventorApp",
    config: "DrawingConfig",
) -> ScanResult:
    """Scan the active assembly and build a list of DrawingItems.

    Uses walk_assembly with all configured filter parameters,
    then checks each component for a co-located .idw file.

    Args:
        app: Connected InventorApp instance.
        config: Drawing tool configuration with scan settings.

    Returns:
        ScanResult with DrawingItems and statistics.
    """
    assembly = app.get_active_assembly()
    discovered = walk_assembly(
        assembly,
        include_suppressed=config.include_suppressed,
        include_content_center=config.include_content_center,
        max_depth=config.max_depth,
        include_parts=config.include_parts,
        include_assemblies=config.include_subassemblies,
    )

    items: list[DrawingItem] = []
    content_center_excluded = 0
    warnings: list[str] = []

    for comp in discovered:
        if comp.is_top_level:
            continue  # skip root assembly itself

        idw = find_idw_path(comp.document.full_path)
        status = DrawingStatus.EXISTING if idw else DrawingStatus.NEEDS_CREATION
        doc_type = "assembly" if isinstance(comp.document, AssemblyDocument) else "part"

        items.append(
            DrawingItem(
                part_path=comp.document.full_path,
                part_name=comp.document.display_name,
                drawing_path=idw,
                drawing_status=status,
                document_type=doc_type,
                depth=comp.depth,
            )
        )

    with_drawings = sum(1 for i in items if i.drawing_status == DrawingStatus.EXISTING)
    without_drawings = sum(1 for i in items if i.drawing_status == DrawingStatus.NEEDS_CREATION)

    logger.info(
        "Scanned %s: %d components, %d with drawings, %d without",
        assembly.display_name,
        len(items),
        with_drawings,
        without_drawings,
    )

    return ScanResult(
        assembly_path=assembly.full_path,
        items=items,
        total_parts=len(items),
        parts_with_drawings=with_drawings,
        parts_without_drawings=without_drawings,
        content_center_excluded=content_center_excluded,
        warnings=warnings,
    )


__all__ = ["scan_assembly_for_release"]
