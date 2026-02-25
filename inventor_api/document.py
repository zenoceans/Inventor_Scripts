"""Pythonic wrappers around Inventor document COM objects."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Iterator

from inventor_api.exceptions import InventorError
from inventor_api.types import DocumentType, PropertySet

if TYPE_CHECKING:
    pass  # COM objects are dynamically typed


class InventorDocument:
    """Wraps an Inventor document COM object.

    Args:
        com_doc: The raw COM document object (e.g., from Inventor.ActiveDocument).
    """

    def __init__(self, com_doc: object) -> None:
        self._com = com_doc

    @property
    def com_object(self) -> object:
        """Access the underlying COM object."""
        return self._com

    @property
    def full_path(self) -> str:
        """Full file path of the document."""
        return str(self._com.FullFileName)

    @property
    def display_name(self) -> str:
        """File name without path or extension."""
        return os.path.splitext(os.path.basename(self.full_path))[0]

    @property
    def document_type(self) -> DocumentType:
        """Document type as a DocumentType enum member."""
        return DocumentType(int(self._com.DocumentType))

    @property
    def is_content_center(self) -> bool:
        """True if the document is from Inventor's Content Center."""
        return "content center files" in self.full_path.lower()

    def get_property(self, prop_set_name: str, prop_name: str) -> str | None:
        """Read a single iProperty value by property set and name.

        Returns None if the property doesn't exist or has no value.
        """
        try:
            prop_sets = self._com.PropertySets
            prop_set = prop_sets.Item(prop_set_name)
            value = prop_set.Item(prop_name).Value
            if value is None:
                return None
            result = str(value).strip()
            return result if result else None
        except Exception:
            return None

    def get_revision(self) -> str:
        """Get the revision number from Design Tracking Properties.

        Returns 'NoRev' if the property is empty or missing.
        """
        value = self.get_property(PropertySet.DESIGN_TRACKING, "Revision Number")
        return value if value else "NoRev"

    def close(self, skip_save: bool = True) -> None:
        """Close the document.

        Args:
            skip_save: If True, close without saving (default).
        """
        try:
            self._com.Close(skip_save)
        except Exception as e:
            raise InventorError(f"Failed to close {self.full_path}: {e}") from e

    def __repr__(self) -> str:
        return f"InventorDocument({self.display_name!r})"


class AssemblyDocument(InventorDocument):
    """Wraps an Inventor assembly document with traversal support."""

    @property
    def occurrences(self) -> Iterator[ComponentOccurrence]:
        """Iterate over top-level component occurrences."""
        comp_def = self._com.ComponentDefinition
        for occ in comp_def.Occurrences:
            yield ComponentOccurrence(occ)

    def __repr__(self) -> str:
        return f"AssemblyDocument({self.display_name!r})"


class ComponentOccurrence:
    """Wraps a single component occurrence in an assembly.

    Args:
        com_occurrence: The raw COM ComponentOccurrence object.
    """

    def __init__(self, com_occurrence: object) -> None:
        self._com = com_occurrence

    @property
    def referenced_document(self) -> InventorDocument:
        """Get the document this occurrence references.

        Returns an AssemblyDocument if the referenced doc is an assembly,
        otherwise a plain InventorDocument.
        """
        ref_doc = self._com.ReferencedDocumentDescriptor.ReferencedDocument
        doc_type = int(ref_doc.DocumentType)
        if doc_type == DocumentType.ASSEMBLY:
            return AssemblyDocument(ref_doc)
        return InventorDocument(ref_doc)

    @property
    def is_suppressed(self) -> bool:
        """True if this occurrence is suppressed."""
        try:
            return bool(self._com.Suppressed)
        except Exception:
            return False

    @property
    def definition_document_type(self) -> DocumentType:
        """Document type of the referenced component."""
        return DocumentType(int(self._com.DefinitionDocumentType))

    def __repr__(self) -> str:
        try:
            name = self.referenced_document.display_name
        except Exception:
            name = "?"
        return f"ComponentOccurrence({name!r})"
