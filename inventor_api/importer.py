"""Import STEP files into Inventor via COM."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from inventor_api.document import AssemblyDocument, InventorDocument
from inventor_api.exceptions import StepImportError
from inventor_api.types import DocumentType

if TYPE_CHECKING:
    from inventor_api.application import InventorApp

_log = logging.getLogger(__name__)


def import_step(
    app: InventorApp,
    step_path: str | Path,
    *,
    visible: bool = True,
) -> InventorDocument:
    """Open a STEP file in Inventor using the native STEP translator.

    Inventor auto-detects STEP format from the file extension when called
    via ``Documents.Open``.  The result is either a PartDocument (``.ipt``)
    or an AssemblyDocument (``.iam``) depending on the STEP content.

    Args:
        app: Connected InventorApp instance.
        step_path: Full path to the ``.stp`` / ``.step`` file.
        visible: Open with a visible window.  Default ``True`` so the user
                 can observe the import.

    Returns:
        Wrapped document — ``AssemblyDocument`` for assemblies,
        ``InventorDocument`` for parts.

    Raises:
        StepImportError: If the file does not exist or cannot be opened.
    """
    step_path = str(step_path)
    if not os.path.isfile(step_path):
        raise StepImportError(
            step_path,
            cause=FileNotFoundError(f"File not found: {step_path}"),
        )
    try:
        com_doc = app.com_app.Documents.Open(step_path, visible)
    except Exception as e:
        raise StepImportError(step_path, cause=e) from e

    doc_type = int(com_doc.DocumentType)
    _log.info("Imported STEP: %s -> %s", step_path, DocumentType(doc_type).name)

    if doc_type == DocumentType.ASSEMBLY:
        return AssemblyDocument(com_doc)
    return InventorDocument(com_doc)


def is_assembly_document(doc: InventorDocument) -> bool:
    """Return True if the document is an assembly (``.iam``)."""
    return doc.document_type == DocumentType.ASSEMBLY
