"""Pythonic wrapper around the Autodesk Inventor COM API.

Example::

    from inventor_api import InventorApp
    from inventor_api.traversal import walk_assembly
    from inventor_api.exporters import export_step

    app = InventorApp.connect()
    assembly = app.get_active_assembly()
    components = walk_assembly(assembly)
    for comp in components:
        export_step(app, comp.document, f"output/{comp.document.display_name}.step")
"""

from inventor_api.application import InventorApp
from inventor_api.document import AssemblyDocument, ComponentOccurrence, InventorDocument
from inventor_api.exceptions import (
    DocumentOpenError,
    ExportError,
    InventorError,
    InventorNotAssemblyError,
    InventorNotRunningError,
    TranslatorError,
)
from inventor_api.traversal import DiscoveredComponent, walk_assembly
from inventor_api.types import DocumentType, PropertySet, TranslatorId

__all__ = [
    "InventorApp",
    "InventorDocument",
    "AssemblyDocument",
    "ComponentOccurrence",
    "DiscoveredComponent",
    "walk_assembly",
    "DocumentType",
    "TranslatorId",
    "PropertySet",
    "InventorError",
    "InventorNotRunningError",
    "InventorNotAssemblyError",
    "DocumentOpenError",
    "ExportError",
    "TranslatorError",
]
