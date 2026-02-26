"""Shared fixtures and mock COM object factories for tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from inventor_api.types import DocumentType


def make_mock_com_document(
    *,
    full_filename: str = r"C:\Projects\Part.ipt",
    document_type: int = DocumentType.PART,
    revision: str = "A",
    properties: dict[str, dict[str, str]] | None = None,
) -> MagicMock:
    """Create a mock COM document object.

    Args:
        full_filename: The FullFileName property.
        document_type: The DocumentType integer.
        revision: Revision Number value in Design Tracking Properties.
        properties: Optional dict of {prop_set_name: {prop_name: value}}.
    """
    doc = MagicMock()
    doc.FullFileName = full_filename
    doc.DocumentType = document_type
    doc.DisplayName = full_filename.rsplit("\\", 1)[-1].rsplit(".", 1)[0]

    # Set up PropertySets
    if properties is None:
        properties = {
            "Design Tracking Properties": {"Revision Number": revision},
        }

    def item_side_effect(set_name):
        prop_set_mock = MagicMock()
        set_data = properties.get(set_name, {})

        def prop_item(name):
            prop_mock = MagicMock()
            prop_mock.Value = set_data.get(name)
            return prop_mock

        prop_set_mock.Item = MagicMock(side_effect=prop_item)
        return prop_set_mock

    doc.PropertySets.Item = MagicMock(side_effect=item_side_effect)
    return doc


def make_mock_com_occurrence(
    *,
    document: MagicMock | None = None,
    suppressed: bool = False,
    doc_type: int = DocumentType.PART,
) -> MagicMock:
    """Create a mock COM ComponentOccurrence.

    Args:
        document: Mock COM document this occurrence references.
        suppressed: Whether the occurrence is suppressed.
        doc_type: DefinitionDocumentType value.
    """
    if document is None:
        document = make_mock_com_document(document_type=doc_type)

    occ = MagicMock()
    occ.Suppressed = suppressed
    occ.DefinitionDocumentType = doc_type
    occ.ReferencedDocumentDescriptor.ReferencedDocument = document
    return occ


def make_mock_assembly_com(
    *,
    full_filename: str = r"C:\Projects\Assembly.iam",
    revision: str = "1",
    occurrences: list[MagicMock] | None = None,
) -> MagicMock:
    """Create a mock COM assembly document with occurrences.

    Args:
        full_filename: Assembly file path.
        revision: Revision number.
        occurrences: List of mock COM occurrences. Empty list if None.
    """
    doc = make_mock_com_document(
        full_filename=full_filename,
        document_type=DocumentType.ASSEMBLY,
        revision=revision,
    )
    if occurrences is None:
        occurrences = []
    doc.ComponentDefinition.Occurrences = occurrences
    return doc


def make_mock_com_app(
    *,
    active_doc: MagicMock | None = None,
) -> MagicMock:
    """Create a mock COM Inventor.Application.

    Args:
        active_doc: Mock COM document to return as ActiveDocument.
    """
    app = MagicMock()
    app.Visible = True
    if active_doc is not None:
        app.ActiveDocument = active_doc
    else:
        app.ActiveDocument = None

    # Set up TransientObjects for export
    transient = MagicMock()
    app.TransientObjects = transient

    return app
