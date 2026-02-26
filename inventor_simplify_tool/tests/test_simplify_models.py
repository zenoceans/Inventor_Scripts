"""Tests for inventor_simplify_tool.models."""

from inventor_simplify_tool.models import SimplifyResult, SimplifyRow, SimplifySummary


class TestSimplifyRow:
    def test_fields(self) -> None:
        row = SimplifyRow(
            step_path=r"C:\test\part.stp",
            output_filename="simplified_part",
            output_folder=r"C:\output",
        )
        assert row.step_path == r"C:\test\part.stp"
        assert row.output_filename == "simplified_part"
        assert row.output_folder == r"C:\output"


class TestSimplifyResult:
    def test_defaults(self) -> None:
        row = SimplifyRow("a.stp", "out", r"C:\out")
        result = SimplifyResult(row=row, success=True)
        assert result.output_path is None
        assert result.imported_as_assembly is False
        assert result.error_message is None
        assert result.duration_seconds == 0.0

    def test_failed_result(self) -> None:
        row = SimplifyRow("a.stp", "out", r"C:\out")
        result = SimplifyResult(row=row, success=False, error_message="COM error")
        assert not result.success
        assert result.error_message == "COM error"


class TestSimplifySummary:
    def test_defaults(self) -> None:
        summary = SimplifySummary(total_rows=5, succeeded=3, failed=2)
        assert summary.results == []

    def test_with_results(self) -> None:
        row = SimplifyRow("a.stp", "out", r"C:\out")
        r1 = SimplifyResult(row=row, success=True)
        r2 = SimplifyResult(row=row, success=False, error_message="err")
        summary = SimplifySummary(total_rows=2, succeeded=1, failed=1, results=[r1, r2])
        assert len(summary.results) == 2
