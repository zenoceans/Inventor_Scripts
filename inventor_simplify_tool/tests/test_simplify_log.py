"""Tests for inventor_simplify_tool.simplify_log."""

from __future__ import annotations

from inventor_simplify_tool.models import SimplifyResult, SimplifyRow, SimplifySummary
from inventor_simplify_tool.simplify_log import SimplifyLogger
from inventor_utils.error_hints import error_hint


def _make_row(step: str = "a.stp", name: str = "out", folder: str = r"C:\out") -> SimplifyRow:
    return SimplifyRow(step_path=step, output_filename=name, output_folder=folder)


class TestErrorHint:
    def test_file_not_found(self) -> None:
        assert "STEP file exists" in error_hint("File not found: C:\\test.stp")

    def test_simplify_failure(self) -> None:
        assert "Simplify" in error_hint("Failed to simplify document")

    def test_save_failure(self) -> None:
        assert "write permissions" in error_hint("Failed to save document")

    def test_com_error(self) -> None:
        assert "COM" in error_hint("COM error: something went wrong")

    def test_unknown_error(self) -> None:
        assert error_hint("something completely unexpected") == ""


class TestSimplifyLogger:
    def test_creates_log_file(self, tmp_path) -> None:
        logger = SimplifyLogger(tmp_path)
        logger.open()
        logger.close()
        assert logger.log_path.exists()
        assert logger.log_path.name.startswith("simplify_log_")

    def test_log_path_property(self, tmp_path) -> None:
        logger = SimplifyLogger(tmp_path)
        assert logger.log_path.parent == tmp_path

    def test_full_workflow(self, tmp_path) -> None:
        logger = SimplifyLogger(tmp_path)
        logger.open()

        from types import SimpleNamespace

        config = SimpleNamespace(add_to_assembly=False, simplify_settings={})
        logger.log_start(config, 2)

        r1 = SimplifyResult(
            row=_make_row("part.stp"),
            success=True,
            output_path=r"C:\out\part.ipt",
            duration_seconds=1.5,
        )
        r2 = SimplifyResult(
            row=_make_row("bad.stp"),
            success=False,
            error_message="File not found: bad.stp",
            duration_seconds=0.1,
        )
        logger.log_result(r1)
        logger.log_result(r2)

        summary = SimplifySummary(total_rows=2, succeeded=1, failed=1, results=[r1, r2])
        logger.log_finish(summary)
        logger.close()

        content = logger.log_path.read_text(encoding="utf-8")
        assert "[OK] part.stp" in content
        assert "[FAILED] bad.stp" in content
        assert "Succeeded: 1" in content
        assert "Failed:    1" in content
        assert "STEP file exists" in content  # error hint

    def test_assembly_import_noted(self, tmp_path) -> None:
        logger = SimplifyLogger(tmp_path)
        logger.open()

        r = SimplifyResult(
            row=_make_row(),
            success=True,
            output_path=r"C:\out\out.ipt",
            imported_as_assembly=True,
            duration_seconds=2.0,
        )
        logger.log_result(r)
        logger.close()

        content = logger.log_path.read_text(encoding="utf-8")
        assert "assembly" in content.lower()

    def test_add_to_assembly_logged(self, tmp_path) -> None:
        logger = SimplifyLogger(tmp_path)
        logger.open()

        from types import SimpleNamespace

        config = SimpleNamespace(
            add_to_assembly=True,
            target_assembly_path=r"C:\target\asm.iam",
        )
        logger.log_start(config, 1)
        logger.close()

        content = logger.log_path.read_text(encoding="utf-8")
        assert r"C:\target\asm.iam" in content
