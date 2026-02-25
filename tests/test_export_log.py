"""Tests for inventor_export_tool.export_log."""

from inventor_export_tool.config import AppConfig
from inventor_export_tool.export_log import ExportLogger, _error_hint
from inventor_export_tool.models import (
    ComponentInfo,
    ExportItem,
    ExportResult,
    ScanSummary,
)


def _make_component(
    source_path: str = r"C:\Projects\Bracket.ipt",
    idw_path: str | None = None,
) -> ComponentInfo:
    return ComponentInfo(
        source_path=source_path,
        display_name="Bracket",
        document_type="part",
        revision="B",
        idw_path=idw_path,
    )


def _make_item(
    filename: str = "Bracket-B.step",
    export_type: str = "step",
    idw_path: str | None = None,
) -> ExportItem:
    return ExportItem(
        component=_make_component(idw_path=idw_path),
        export_type=export_type,
        output_filename=filename,
        output_path=rf"C:\output\{filename}",
    )


def _make_result(
    success: bool = True,
    error: str | None = None,
    export_type: str = "step",
    idw_path: str | None = None,
) -> ExportResult:
    return ExportResult(
        item=_make_item(export_type=export_type, idw_path=idw_path),
        success=success,
        error_message=error,
        duration_seconds=1.5,
    )


def _make_config(**overrides) -> AppConfig:
    defaults = {
        "output_folder": r"C:\output",
        "export_options": {
            "step": {"ApplicationProtocolType": 3},
            "pdf": {"Vector_Resolution": 400},
        },
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


class TestLogConfig:
    def test_writes_header(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        logger.log_config(_make_config(), "MyAssembly", r"C:\Projects\MyAssembly.iam")
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "INVENTOR EXPORT LOG" in content
        assert "Assembly: MyAssembly" in content
        assert r"C:\Projects\MyAssembly.iam" in content

    def test_writes_settings(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        config = _make_config(export_step=True, export_dwg=False, export_pdf=True)
        logger.log_config(config, "Asm", "path")
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "STEP, PDF" in content
        assert "DWG" not in content.split("EXPORT OPTIONS")[0].split("Formats:")[1]

    def test_writes_export_options(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        logger.log_config(_make_config(), "Asm", "path")
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "ApplicationProtocolType=3" in content
        assert "Vector_Resolution=400" in content
        assert "DWG:  (Inventor defaults)" in content

    def test_writes_include_exclude(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        logger.log_config(
            _make_config(include_parts=True, include_suppressed=False),
            "Asm",
            "path",
        )
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "parts" in content
        assert "suppressed" in content


class TestLogStart:
    def test_writes_scan_results(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        summary = ScanSummary(
            total_components=10,
            content_center_excluded=3,
            suppressed_excluded=1,
            export_items=[_make_item()],
            warnings=["Duplicate resolved"],
        )
        logger.log_start(summary)
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "Components found:        10" in content
        assert "Content Center excluded: 3" in content
        assert "Files to export:         1" in content
        assert "Duplicate resolved" in content


class TestLogExport:
    def test_success_includes_source(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        result = _make_result(success=True)
        logger.log_export(result)
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "[OK]" in content
        assert "Bracket-B.step" in content
        assert r"C:\Projects\Bracket.ipt" in content

    def test_failure_includes_error_and_hint(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        result = _make_result(
            success=False, error="Failed to open document: C:\\Projects\\Bracket.idw"
        )
        logger.log_export(result)
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "[FAILED]" in content
        assert "Failed to open document" in content
        assert "Hint:" in content
        assert "not open in another program" in content

    def test_drawing_export_includes_idw_path(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        result = _make_result(
            success=True,
            export_type="dwg",
            idw_path=r"C:\Projects\Bracket.idw",
        )
        logger.log_export(result)
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "Drawing:" in content
        assert r"C:\Projects\Bracket.idw" in content


class TestLogFinish:
    def test_summary_with_failures(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        results = [
            _make_result(success=True),
            _make_result(success=False, error="Some error"),
        ]
        logger.log_finish(results)
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "Succeeded: 1" in content
        assert "Failed: 1" in content
        assert "FAILED ITEMS" in content
        assert "Some error" in content
        assert "Hint:" in content

    def test_includes_config_tip(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        logger.log_finish([_make_result(success=True)])
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "config.json" in content
        assert "README.md" in content


class TestErrorHint:
    def test_open_document_hint(self):
        hint = _error_hint("Failed to open document: C:\\file.idw")
        assert "not open in another program" in hint

    def test_idw_not_found_hint(self):
        hint = _error_hint("No IDW file found")
        assert "IDW drawing file" in hint

    def test_translator_hint(self):
        hint = _error_hint("Translator add-in not found")
        assert "installed correctly" in hint

    def test_doc_not_in_memory_hint(self):
        hint = _error_hint("Document not found in memory")
        assert "scanning again" in hint

    def test_fallback_hint(self):
        hint = _error_hint("Unknown error occurred")
        assert "try again" in hint


class TestWriteWithoutOpen:
    def test_raises(self, tmp_path):
        import pytest

        logger = ExportLogger(tmp_path)
        with pytest.raises(RuntimeError, match="Logger not opened"):
            logger.log_export(_make_result())


class TestFullLifecycle:
    def test_complete_log(self, tmp_path):
        logger = ExportLogger(tmp_path)
        logger.open()
        logger.log_config(_make_config(), "TestAsm", r"C:\Projects\TestAsm.iam")
        summary = ScanSummary(
            total_components=2,
            content_center_excluded=0,
            suppressed_excluded=0,
            export_items=[_make_item()],
        )
        logger.log_start(summary)
        result = _make_result(success=True)
        logger.log_export(result)
        logger.log_finish([result])
        logger.close()
        content = logger.log_path.read_text(encoding="utf-8")
        assert "INVENTOR EXPORT LOG" in content
        assert "TestAsm" in content
        assert "SCAN RESULTS" in content
        assert "[OK]" in content
        assert "SUMMARY" in content
        assert "config.json" in content
