"""Tests for inventor_api.importer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from inventor_api.application import InventorApp
from inventor_api.document import AssemblyDocument, InventorDocument
from inventor_api.exceptions import StepImportError
from inventor_api.importer import import_step, is_assembly_document
from inventor_api.types import DocumentType


def _make_mock_app(*, doc_type: int = DocumentType.PART) -> tuple[InventorApp, MagicMock]:
    """Create a mock InventorApp whose Documents.Open returns a doc of the given type."""
    com_app = MagicMock()
    com_doc = MagicMock()
    com_doc.DocumentType = doc_type
    com_app.Documents.Open.return_value = com_doc
    return InventorApp(com_app), com_doc


class TestImportStep:
    def test_import_part(self, tmp_path) -> None:
        stp = tmp_path / "part.stp"
        stp.write_text("dummy")
        app, com_doc = _make_mock_app(doc_type=DocumentType.PART)

        doc = import_step(app, str(stp))

        assert isinstance(doc, InventorDocument)
        assert not isinstance(doc, AssemblyDocument)
        app.com_app.Documents.Open.assert_called_once_with(str(stp), True)

    def test_import_assembly(self, tmp_path) -> None:
        stp = tmp_path / "asm.stp"
        stp.write_text("dummy")
        app, com_doc = _make_mock_app(doc_type=DocumentType.ASSEMBLY)

        doc = import_step(app, str(stp))

        assert isinstance(doc, AssemblyDocument)

    def test_import_invisible(self, tmp_path) -> None:
        stp = tmp_path / "part.stp"
        stp.write_text("dummy")
        app, _ = _make_mock_app()

        import_step(app, str(stp), visible=False)

        app.com_app.Documents.Open.assert_called_once_with(str(stp), False)

    def test_file_not_found(self) -> None:
        app, _ = _make_mock_app()
        with pytest.raises(StepImportError, match="File not found"):
            import_step(app, r"C:\nonexistent\fake.stp")

    def test_com_error_wrapped(self, tmp_path) -> None:
        stp = tmp_path / "bad.stp"
        stp.write_text("dummy")
        app, _ = _make_mock_app()
        app.com_app.Documents.Open.side_effect = Exception("COM failure")

        with pytest.raises(StepImportError, match="COM failure"):
            import_step(app, str(stp))

    def test_accepts_path_object(self, tmp_path) -> None:
        stp = tmp_path / "part.stp"
        stp.write_text("dummy")
        app, _ = _make_mock_app()

        doc = import_step(app, stp)  # Path, not str
        assert isinstance(doc, InventorDocument)


class TestIsAssemblyDocument:
    def test_assembly(self) -> None:
        com_doc = MagicMock()
        com_doc.DocumentType = DocumentType.ASSEMBLY
        doc = AssemblyDocument(com_doc)
        assert is_assembly_document(doc) is True

    def test_part(self) -> None:
        com_doc = MagicMock()
        com_doc.DocumentType = DocumentType.PART
        doc = InventorDocument(com_doc)
        assert is_assembly_document(doc) is False
