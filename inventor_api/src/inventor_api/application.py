"""Inventor application connection and lifecycle management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inventor_api.document import AssemblyDocument, InventorDocument
from inventor_api.exceptions import (
    DocumentOpenError,
    InventorNotAssemblyError,
    InventorNotRunningError,
)
from inventor_api.types import DocumentType

if TYPE_CHECKING:
    from inventor_api.drawing import DrawingDocument


class InventorApp:
    """Pythonic wrapper around the Inventor.Application COM object.

    Can be created by connecting to a running instance, or by injecting
    a mock COM object for testing.

    Example::

        app = InventorApp.connect()
        doc = app.active_document
        print(doc.display_name)
    """

    def __init__(self, com_app: object) -> None:
        """Create wrapper around an existing COM Application object.

        Args:
            com_app: The raw Inventor.Application COM object.
        """
        self._com = com_app

    @property
    def com_app(self) -> object:
        """Access the underlying COM Application object."""
        return self._com

    @classmethod
    def connect(cls) -> InventorApp:
        """Connect to a running Inventor instance.

        Raises:
            InventorNotRunningError: If Inventor is not running.
        """
        try:
            import win32com.client

            com_app = win32com.client.Dispatch("Inventor.Application")
            # Verify the connection is alive by accessing a property
            _ = com_app.Visible
            return cls(com_app)
        except Exception as e:
            raise InventorNotRunningError(
                f"Could not connect to Inventor. Is it running? ({e})"
            ) from e

    @staticmethod
    def is_running() -> bool:
        """Check if Inventor is currently running.

        Returns True if a running Inventor instance can be found.
        """
        try:
            import win32com.client

            win32com.client.GetActiveObject("Inventor.Application")
            return True
        except Exception:
            return False

    @property
    def active_document(self) -> InventorDocument:
        """Get the currently active document.

        Returns an AssemblyDocument if the active doc is an assembly,
        or a DrawingDocument if it is a drawing.

        Raises:
            InventorError: If no document is open.
        """
        try:
            doc = self._com.ActiveDocument
            if doc is None:
                raise InventorNotRunningError("No document is currently open in Inventor.")
        except InventorNotRunningError:
            raise
        except Exception as e:
            raise InventorNotRunningError(f"Could not get active document: {e}") from e

        doc_type = int(doc.DocumentType)
        if doc_type == DocumentType.ASSEMBLY:
            return AssemblyDocument(doc)
        if doc_type == DocumentType.DRAWING:
            from inventor_api.drawing import DrawingDocument

            return DrawingDocument(doc)
        return InventorDocument(doc)

    def get_active_assembly(self) -> AssemblyDocument:
        """Get the active document, verifying it is an assembly.

        Raises:
            InventorNotAssemblyError: If the active document is not an assembly.
        """
        doc = self.active_document
        if not isinstance(doc, AssemblyDocument):
            raise InventorNotAssemblyError(
                f"Active document '{doc.display_name}' is not an assembly "
                f"(type: {doc.document_type.name})."
            )
        return doc

    def open_document(self, path: str, visible: bool = False) -> InventorDocument:
        """Open a document in Inventor.

        Args:
            path: Full file path to the document.
            visible: If False (default), open invisibly without creating a window.

        Returns:
            Wrapped document (AssemblyDocument if it's an assembly).

        Raises:
            DocumentOpenError: If the document can't be opened.
        """
        try:
            # Documents.Open(FileName, OpenVisible)
            # OpenVisible=True creates a window, False opens invisibly
            com_doc = self._com.Documents.Open(path, visible)
        except Exception as e:
            raise DocumentOpenError(path, cause=e) from e

        doc_type = int(com_doc.DocumentType)
        if doc_type == DocumentType.ASSEMBLY:
            return AssemblyDocument(com_doc)
        if doc_type == DocumentType.DRAWING:
            from inventor_api.drawing import DrawingDocument

            return DrawingDocument(com_doc)
        return InventorDocument(com_doc)

    def create_drawing(self, template_path: str) -> "DrawingDocument":
        """Create a new drawing document from a template.

        Args:
            template_path: Full path to the .idw template file.

        Returns:
            A DrawingDocument wrapping the newly created document.

        Raises:
            DrawingCreationError: If creation fails.
        """
        from inventor_api.drawing import DrawingDocument
        from inventor_api.exceptions import DrawingCreationError

        try:
            com_doc = self._com.Documents.Add(DocumentType.DRAWING, template_path, True)
            return DrawingDocument(com_doc)
        except Exception as e:
            raise DrawingCreationError(template_path, cause=e) from e

    def __repr__(self) -> str:
        return "InventorApp(connected)"
