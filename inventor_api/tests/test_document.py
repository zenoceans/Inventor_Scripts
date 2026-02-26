"""Tests for inventor_api.document module."""

from conftest import make_mock_assembly_com, make_mock_com_document, make_mock_com_occurrence

from inventor_api.document import AssemblyDocument, ComponentOccurrence, InventorDocument
from inventor_api.types import DocumentType


class TestInventorDocument:
    def test_full_path(self):
        com = make_mock_com_document(full_filename=r"C:\Projects\Bracket.ipt")
        doc = InventorDocument(com)
        assert doc.full_path == r"C:\Projects\Bracket.ipt"

    def test_display_name(self):
        com = make_mock_com_document(full_filename=r"C:\Projects\Bracket.ipt")
        doc = InventorDocument(com)
        assert doc.display_name == "Bracket"

    def test_document_type_part(self):
        com = make_mock_com_document(document_type=DocumentType.PART)
        doc = InventorDocument(com)
        assert doc.document_type == DocumentType.PART

    def test_document_type_assembly(self):
        com = make_mock_com_document(document_type=DocumentType.ASSEMBLY)
        doc = InventorDocument(com)
        assert doc.document_type == DocumentType.ASSEMBLY

    def test_is_content_center_true(self):
        com = make_mock_com_document(full_filename=r"C:\Content Center Files\Fasteners\bolt.ipt")
        doc = InventorDocument(com)
        assert doc.is_content_center is True

    def test_is_content_center_false(self):
        com = make_mock_com_document(full_filename=r"C:\Projects\Bracket.ipt")
        doc = InventorDocument(com)
        assert doc.is_content_center is False

    def test_get_revision(self):
        com = make_mock_com_document(revision="B")
        doc = InventorDocument(com)
        assert doc.get_revision() == "B"

    def test_get_revision_empty(self):
        com = make_mock_com_document(revision="")
        doc = InventorDocument(com)
        assert doc.get_revision() == "NoRev"

    def test_get_revision_none(self):
        com = make_mock_com_document(
            properties={"Design Tracking Properties": {"Revision Number": None}}
        )
        doc = InventorDocument(com)
        assert doc.get_revision() == "NoRev"

    def test_get_property(self):
        com = make_mock_com_document(
            properties={
                "Design Tracking Properties": {
                    "Revision Number": "C",
                    "Part Number": "BRK-001",
                }
            }
        )
        doc = InventorDocument(com)
        assert doc.get_property("Design Tracking Properties", "Part Number") == "BRK-001"

    def test_get_property_missing(self):
        com = make_mock_com_document()
        # Access a property set that doesn't exist in our mock
        doc = InventorDocument(com)
        # Our mock returns None for missing properties
        result = doc.get_property("Design Tracking Properties", "Nonexistent")
        assert result is None

    def test_close(self):
        com = make_mock_com_document()
        doc = InventorDocument(com)
        doc.close(skip_save=True)
        com.Close.assert_called_once_with(True)

    def test_repr(self):
        com = make_mock_com_document(full_filename=r"C:\Projects\Bracket.ipt")
        doc = InventorDocument(com)
        assert "Bracket" in repr(doc)

    def test_com_object_access(self):
        com = make_mock_com_document()
        doc = InventorDocument(com)
        assert doc.com_object is com


class TestAssemblyDocument:
    def test_occurrences(self):
        occ1 = make_mock_com_occurrence()
        occ2 = make_mock_com_occurrence()
        asm_com = make_mock_assembly_com(occurrences=[occ1, occ2])
        asm = AssemblyDocument(asm_com)
        occs = list(asm.occurrences)
        assert len(occs) == 2
        assert all(isinstance(o, ComponentOccurrence) for o in occs)

    def test_empty_assembly(self):
        asm_com = make_mock_assembly_com(occurrences=[])
        asm = AssemblyDocument(asm_com)
        assert list(asm.occurrences) == []

    def test_repr(self):
        asm_com = make_mock_assembly_com(full_filename=r"C:\Projects\TopAsm.iam")
        asm = AssemblyDocument(asm_com)
        assert "TopAsm" in repr(asm)


class TestComponentOccurrence:
    def test_referenced_document_part(self):
        doc_com = make_mock_com_document(
            full_filename=r"C:\Projects\Part.ipt", document_type=DocumentType.PART
        )
        occ_com = make_mock_com_occurrence(document=doc_com, doc_type=DocumentType.PART)
        occ = ComponentOccurrence(occ_com)
        ref = occ.referenced_document
        assert isinstance(ref, InventorDocument)
        assert ref.full_path == r"C:\Projects\Part.ipt"

    def test_referenced_document_assembly(self):
        sub_asm_com = make_mock_assembly_com(full_filename=r"C:\Projects\SubAsm.iam")
        occ_com = make_mock_com_occurrence(document=sub_asm_com, doc_type=DocumentType.ASSEMBLY)
        occ = ComponentOccurrence(occ_com)
        ref = occ.referenced_document
        assert isinstance(ref, AssemblyDocument)

    def test_is_suppressed(self):
        occ_com = make_mock_com_occurrence(suppressed=True)
        occ = ComponentOccurrence(occ_com)
        assert occ.is_suppressed is True

    def test_not_suppressed(self):
        occ_com = make_mock_com_occurrence(suppressed=False)
        occ = ComponentOccurrence(occ_com)
        assert occ.is_suppressed is False

    def test_definition_document_type(self):
        occ_com = make_mock_com_occurrence(doc_type=DocumentType.ASSEMBLY)
        occ = ComponentOccurrence(occ_com)
        assert occ.definition_document_type == DocumentType.ASSEMBLY
