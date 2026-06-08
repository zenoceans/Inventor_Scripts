"""Tests for InventorApp active-document accessors."""

from __future__ import annotations

import pytest

from conftest import (
    make_mock_assembly_com,
    make_mock_com_app,
    make_mock_com_document,
)

from inventor_api.application import InventorApp
from inventor_api.document import AssemblyDocument, InventorDocument
from inventor_api.exceptions import InventorNotPartOrAssemblyError
from inventor_api.types import DocumentType


def test_get_active_part_or_assembly_returns_assembly():
    com_app = make_mock_com_app(active_doc=make_mock_assembly_com())
    app = InventorApp(com_app)

    doc = app.get_active_part_or_assembly()

    assert isinstance(doc, AssemblyDocument)


def test_get_active_part_or_assembly_returns_part():
    part_com = make_mock_com_document(document_type=DocumentType.PART)
    com_app = make_mock_com_app(active_doc=part_com)
    app = InventorApp(com_app)

    doc = app.get_active_part_or_assembly()

    assert isinstance(doc, InventorDocument)
    assert doc.document_type == DocumentType.PART


def test_get_active_part_or_assembly_rejects_drawing():
    drawing_com = make_mock_com_document(document_type=DocumentType.DRAWING)
    com_app = make_mock_com_app(active_doc=drawing_com)
    app = InventorApp(com_app)

    with pytest.raises(InventorNotPartOrAssemblyError):
        app.get_active_part_or_assembly()
