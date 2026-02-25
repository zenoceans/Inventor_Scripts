"""Tests for inventor_api.types and inventor_api.exceptions."""

import pytest

from inventor_api.types import DocumentType, TranslatorId, IO_MECHANISM, PropertySet
from inventor_api.exceptions import (
    InventorError,
    InventorNotRunningError,
    InventorNotAssemblyError,
    DocumentOpenError,
    ExportError,
    TranslatorError,
)


class TestDocumentType:
    def test_part_value(self):
        assert DocumentType.PART == 12290

    def test_assembly_value(self):
        assert DocumentType.ASSEMBLY == 12291

    def test_drawing_value(self):
        assert DocumentType.DRAWING == 12292

    def test_from_int(self):
        assert DocumentType(12290) is DocumentType.PART

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            DocumentType(99999)


class TestTranslatorId:
    def test_step_guid(self):
        assert TranslatorId.STEP == "{90AF7F40-0C01-11D5-8E83-0010B541CD80}"

    def test_dwg_guid(self):
        assert TranslatorId.DWG == "{C24E3AC4-122E-11D5-8E91-0010B541CD80}"

    def test_pdf_guid(self):
        assert TranslatorId.PDF == "{0AC6FD96-2F4D-42CE-8BE0-8AEA580399E4}"

    def test_is_string(self):
        assert isinstance(TranslatorId.STEP, str)
        assert TranslatorId.STEP.startswith("{")


class TestIOMechanism:
    def test_value(self):
        assert IO_MECHANISM == 13059


class TestPropertySet:
    def test_design_tracking(self):
        assert PropertySet.DESIGN_TRACKING == "Design Tracking Properties"


class TestExceptionHierarchy:
    def test_base_is_exception(self):
        assert issubclass(InventorError, Exception)

    def test_not_running_inherits(self):
        assert issubclass(InventorNotRunningError, InventorError)

    def test_not_assembly_inherits(self):
        assert issubclass(InventorNotAssemblyError, InventorError)

    def test_export_error_inherits(self):
        assert issubclass(ExportError, InventorError)

    def test_translator_error_inherits(self):
        assert issubclass(TranslatorError, ExportError)

    def test_document_open_error_inherits(self):
        assert issubclass(DocumentOpenError, InventorError)


class TestDocumentOpenError:
    def test_message(self):
        err = DocumentOpenError(r"C:\test.ipt")
        assert "C:\\test.ipt" in str(err)

    def test_with_cause(self):
        cause = RuntimeError("file locked")
        err = DocumentOpenError(r"C:\test.ipt", cause=cause)
        assert "file locked" in str(err)
        assert err.cause is cause
        assert err.path == r"C:\test.ipt"


class TestExportError:
    def test_message(self):
        err = ExportError(r"C:\test.ipt", "step")
        assert "test.ipt" in str(err)
        assert "step" in str(err)

    def test_with_cause(self):
        cause = RuntimeError("translator busy")
        err = ExportError(r"C:\test.ipt", "pdf", cause=cause)
        assert "translator busy" in str(err)
        assert err.format == "pdf"
