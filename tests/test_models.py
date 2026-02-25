"""Tests for inventor_export_tool.models."""

from inventor_export_tool.models import (
    ComponentInfo,
    ExportItem,
    ExportResult,
    ScanSummary,
)


def _make_component(**overrides) -> ComponentInfo:
    defaults = {
        "source_path": r"C:\Projects\Bracket.ipt",
        "display_name": "Bracket",
        "document_type": "part",
        "revision": "B",
    }
    defaults.update(overrides)
    return ComponentInfo(**defaults)


def _make_export_item(**overrides) -> ExportItem:
    comp = overrides.pop("component", _make_component())
    defaults = {
        "component": comp,
        "export_type": "step",
        "output_filename": "Bracket-B.step",
        "output_path": r"C:\output\Bracket-B.step",
    }
    defaults.update(overrides)
    return ExportItem(**defaults)


class TestComponentInfo:
    def test_construction(self):
        c = _make_component()
        assert c.source_path == r"C:\Projects\Bracket.ipt"
        assert c.display_name == "Bracket"
        assert c.document_type == "part"
        assert c.revision == "B"

    def test_defaults(self):
        c = _make_component()
        assert c.is_top_level is False
        assert c.idw_path is None
        assert c.is_content_center is False
        assert c.is_suppressed is False

    def test_top_level_assembly(self):
        c = _make_component(
            document_type="assembly",
            is_top_level=True,
            idw_path=r"C:\Projects\Bracket.idw",
        )
        assert c.document_type == "assembly"
        assert c.is_top_level is True
        assert c.idw_path == r"C:\Projects\Bracket.idw"

    def test_equality(self):
        a = _make_component()
        b = _make_component()
        assert a == b

    def test_inequality(self):
        a = _make_component(revision="A")
        b = _make_component(revision="B")
        assert a != b


class TestExportItem:
    def test_construction(self):
        item = _make_export_item()
        assert item.export_type == "step"
        assert item.output_filename == "Bracket-B.step"

    def test_component_reference(self):
        comp = _make_component()
        item = _make_export_item(component=comp)
        assert item.component is comp


class TestExportResult:
    def test_success(self):
        item = _make_export_item()
        result = ExportResult(item=item, success=True, duration_seconds=1.5)
        assert result.success is True
        assert result.error_message is None
        assert result.duration_seconds == 1.5

    def test_failure(self):
        item = _make_export_item()
        result = ExportResult(
            item=item, success=False, error_message="COM error", duration_seconds=0.1
        )
        assert result.success is False
        assert result.error_message == "COM error"


class TestScanSummary:
    def test_empty_scan(self):
        s = ScanSummary(total_components=0, content_center_excluded=0, suppressed_excluded=0)
        assert s.export_items == []
        assert s.warnings == []

    def test_with_items(self):
        items = [_make_export_item(), _make_export_item(export_type="dwg")]
        s = ScanSummary(
            total_components=5,
            content_center_excluded=2,
            suppressed_excluded=1,
            export_items=items,
            warnings=["Duplicate filename resolved"],
        )
        assert s.total_components == 5
        assert len(s.export_items) == 2
        assert len(s.warnings) == 1
