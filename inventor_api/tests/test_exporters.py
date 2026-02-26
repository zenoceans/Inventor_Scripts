"""Tests for inventor_api.exporters module."""

import logging
from unittest.mock import MagicMock

import pytest

from conftest import make_mock_com_app, make_mock_com_document

from inventor_api.application import InventorApp
from inventor_api.document import InventorDocument
from inventor_api.exceptions import ExportError, TranslatorError
from inventor_api.exporters import (
    _apply_option_overrides,
    _do_export,
    _get_translator,
    _is_document_open,
    export_dwg,
    export_pdf,
    export_step,
)
from inventor_api.types import TranslatorId


class TestGetTranslator:
    def test_success(self):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        _get_translator(app, TranslatorId.STEP)
        com_app.ApplicationAddIns.ItemById.assert_called_once_with(TranslatorId.STEP.value)

    def test_not_found_raises(self):
        com_app = make_mock_com_app()
        com_app.ApplicationAddIns.ItemById.side_effect = Exception("Not found")
        app = InventorApp(com_app)
        with pytest.raises(TranslatorError):
            _get_translator(app, TranslatorId.STEP)


class TestDoExport:
    def test_calls_save_copy_as(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        com_doc = make_mock_com_document()
        doc = InventorDocument(com_doc)

        output = str(tmp_path / "out.step")
        _do_export(app, doc, output, TranslatorId.STEP)

        # Verify translator was looked up
        com_app.ApplicationAddIns.ItemById.assert_called_with(TranslatorId.STEP.value)

        # Verify SaveCopyAs was called
        translator = com_app.ApplicationAddIns.ItemById.return_value
        translator.SaveCopyAs.assert_called_once()

    def test_raises_export_error_on_failure(self, tmp_path):
        com_app = make_mock_com_app()
        translator = com_app.ApplicationAddIns.ItemById.return_value
        translator.SaveCopyAs.side_effect = Exception("COM failure")

        app = InventorApp(com_app)
        com_doc = make_mock_com_document()
        doc = InventorDocument(com_doc)

        with pytest.raises(ExportError, match="COM failure"):
            _do_export(app, doc, str(tmp_path / "out.step"), TranslatorId.STEP)

    def test_creates_output_directory(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        com_doc = make_mock_com_document()
        doc = InventorDocument(com_doc)

        nested = tmp_path / "sub" / "dir" / "out.step"
        _do_export(app, doc, str(nested), TranslatorId.STEP)
        assert (tmp_path / "sub" / "dir").is_dir()


class TestExportFunctions:
    def test_export_step_uses_step_translator(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())

        export_step(app, doc, tmp_path / "out.step")
        com_app.ApplicationAddIns.ItemById.assert_called_with(TranslatorId.STEP.value)

    def test_export_dwg_uses_dwg_translator(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())

        export_dwg(app, doc, tmp_path / "out.dwg")
        com_app.ApplicationAddIns.ItemById.assert_called_with(TranslatorId.DWG.value)

    def test_export_pdf_uses_pdf_translator(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())

        export_pdf(app, doc, tmp_path / "out.pdf")
        com_app.ApplicationAddIns.ItemById.assert_called_with(TranslatorId.PDF.value)


class TestApplyOptionOverrides:
    def test_invokes_property_put_for_each_override(self):
        options = MagicMock()
        overrides = {"ApplicationProtocolType": 3, "Author": "Test"}
        failed = _apply_option_overrides(options, overrides)

        assert failed == []
        calls = options._oleobj_.Invoke.call_args_list
        assert len(calls) == 2
        # DISPATCH_PROPERTYPUT = 4, DISPID_VALUE = 0
        assert calls[0] == ((0, 0, 4, False, "ApplicationProtocolType", 3),)
        assert calls[1] == ((0, 0, 4, False, "Author", "Test"),)

    def test_empty_overrides_no_invoke(self):
        options = MagicMock()
        failed = _apply_option_overrides(options, {})
        assert failed == []
        options._oleobj_.Invoke.assert_not_called()

    def test_returns_failed_option_keys(self):
        options = MagicMock()
        options._oleobj_.Invoke.side_effect = [None, Exception("COM error"), None]
        overrides = {"Good": 1, "Bad": 2, "AlsoGood": 3}
        failed = _apply_option_overrides(options, overrides)
        assert failed == ["Bad"]
        assert options._oleobj_.Invoke.call_count == 3


class TestDoExportWithOptions:
    def test_option_overrides_applied(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())
        output = str(tmp_path / "out.step")

        overrides = {"ApplicationProtocolType": 3}
        _do_export(app, doc, output, TranslatorId.STEP, option_overrides=overrides)

        # Verify the options NameValueMap had Invoke called for property put
        options = com_app.TransientObjects.CreateNameValueMap.return_value
        options._oleobj_.Invoke.assert_called_once_with(
            0, 0, 4, False, "ApplicationProtocolType", 3
        )

    def test_no_overrides_skips_apply(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())
        output = str(tmp_path / "out.step")

        _do_export(app, doc, output, TranslatorId.STEP)

        options = com_app.TransientObjects.CreateNameValueMap.return_value
        options._oleobj_.Invoke.assert_not_called()

    def test_logs_warning_for_failed_options(self, tmp_path, caplog):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())
        output = str(tmp_path / "out.step")

        options = com_app.TransientObjects.CreateNameValueMap.return_value
        options._oleobj_.Invoke.side_effect = Exception("COM error")

        with caplog.at_level(logging.WARNING, logger="inventor_api.exporters"):
            _do_export(
                app,
                doc,
                output,
                TranslatorId.STEP,
                option_overrides={"BadOption": 1},
            )

        assert "BadOption" in caplog.text
        assert "not supported" in caplog.text


class TestExportFunctionsPassOptions:
    def test_export_step_passes_options(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())
        opts = {"ApplicationProtocolType": 3}

        export_step(app, doc, tmp_path / "out.step", options=opts)

        options = com_app.TransientObjects.CreateNameValueMap.return_value
        options._oleobj_.Invoke.assert_called_once()

    def test_export_dwg_passes_options(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())
        opts = {"Export_Acad_IniFile": "C:\\settings.ini"}

        export_dwg(app, doc, tmp_path / "out.dwg", options=opts)

        options = com_app.TransientObjects.CreateNameValueMap.return_value
        options._oleobj_.Invoke.assert_called_once()

    def test_export_pdf_passes_options(self, tmp_path):
        com_app = make_mock_com_app()
        app = InventorApp(com_app)
        doc = InventorDocument(make_mock_com_document())
        opts = {"Vector_Resolution": 400}

        export_pdf(app, doc, tmp_path / "out.pdf", options=opts)

        options = com_app.TransientObjects.CreateNameValueMap.return_value
        options._oleobj_.Invoke.assert_called_once()


class TestIsDocumentOpen:
    def test_open_document_found(self):
        com_app = make_mock_com_app()
        mock_doc = MagicMock()
        mock_doc.FullFileName = r"C:\Projects\Part.ipt"
        com_app.Documents = [mock_doc]
        app = InventorApp(com_app)

        assert _is_document_open(app, r"C:\Projects\Part.ipt") is True

    def test_document_not_found(self):
        com_app = make_mock_com_app()
        com_app.Documents = []
        app = InventorApp(com_app)

        assert _is_document_open(app, r"C:\Projects\Other.ipt") is False
