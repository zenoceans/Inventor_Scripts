"""Tests for inventor_drawing_tool.models."""

from inventor_drawing_tool.models import (
    DrawingItem,
    DrawingStatus,
    CreationSummary,
    CreationItemResult,
    RevisionData,
    ScanResult,
)


def _make_drawing_item(**overrides) -> DrawingItem:
    defaults = {
        "part_path": r"C:\Projects\Bracket.ipt",
        "part_name": "Bracket",
        "drawing_path": r"C:\Projects\Bracket.idw",
        "drawing_status": DrawingStatus.EXISTING,
        "document_type": "part",
        "depth": 1,
    }
    defaults.update(overrides)
    return DrawingItem(**defaults)


class TestDrawingStatus:
    def test_existing_value(self):
        assert DrawingStatus.EXISTING == "existing"

    def test_needs_creation_value(self):
        assert DrawingStatus.NEEDS_CREATION == "new"

    def test_is_str_enum(self):
        assert isinstance(DrawingStatus.EXISTING, str)
        assert isinstance(DrawingStatus.NEEDS_CREATION, str)

    def test_from_string(self):
        assert DrawingStatus("existing") is DrawingStatus.EXISTING
        assert DrawingStatus("new") is DrawingStatus.NEEDS_CREATION


class TestDrawingItem:
    def test_construction(self):
        item = _make_drawing_item()
        assert item.part_path == r"C:\Projects\Bracket.ipt"
        assert item.part_name == "Bracket"
        assert item.drawing_path == r"C:\Projects\Bracket.idw"
        assert item.drawing_status is DrawingStatus.EXISTING
        assert item.document_type == "part"
        assert item.depth == 1

    def test_default_include(self):
        item = _make_drawing_item()
        assert item.include is True

    def test_no_drawing(self):
        item = _make_drawing_item(
            drawing_path=None,
            drawing_status=DrawingStatus.NEEDS_CREATION,
        )
        assert item.drawing_path is None
        assert item.drawing_status is DrawingStatus.NEEDS_CREATION

    def test_assembly_document_type(self):
        item = _make_drawing_item(document_type="assembly", depth=0)
        assert item.document_type == "assembly"
        assert item.depth == 0

    def test_excluded(self):
        item = _make_drawing_item(include=False)
        assert item.include is False

    def test_equality(self):
        a = _make_drawing_item()
        b = _make_drawing_item()
        assert a == b

    def test_inequality(self):
        a = _make_drawing_item(part_name="Bracket")
        b = _make_drawing_item(part_name="Plate")
        assert a != b


class TestRevisionData:
    def test_defaults(self):
        r = RevisionData()
        assert r.rev_number == ""
        assert r.rev_description == ""
        assert r.made_by == ""
        assert r.approved_by == ""

    def test_construction(self):
        r = RevisionData(
            rev_number="A",
            rev_description="Initial release",
            made_by="OJB",
            approved_by="KAS",
        )
        assert r.rev_number == "A"
        assert r.rev_description == "Initial release"
        assert r.made_by == "OJB"
        assert r.approved_by == "KAS"

    def test_equality(self):
        a = RevisionData(rev_number="A")
        b = RevisionData(rev_number="A")
        assert a == b


class TestScanResult:
    def test_defaults(self):
        s = ScanResult(assembly_path=r"C:\Projects\Assembly.iam")
        assert s.items == []
        assert s.total_parts == 0
        assert s.parts_with_drawings == 0
        assert s.parts_without_drawings == 0
        assert s.content_center_excluded == 0
        assert s.warnings == []

    def test_with_items(self):
        items = [
            _make_drawing_item(),
            _make_drawing_item(drawing_path=None, drawing_status=DrawingStatus.NEEDS_CREATION),
        ]
        s = ScanResult(
            assembly_path=r"C:\Projects\Assembly.iam",
            items=items,
            total_parts=10,
            parts_with_drawings=8,
            parts_without_drawings=2,
            content_center_excluded=3,
            warnings=["Suppressed part skipped"],
        )
        assert len(s.items) == 2
        assert s.total_parts == 10
        assert s.parts_with_drawings == 8
        assert s.parts_without_drawings == 2
        assert s.content_center_excluded == 3
        assert len(s.warnings) == 1

    def test_items_list_not_shared(self):
        s1 = ScanResult(assembly_path="A.iam")
        s2 = ScanResult(assembly_path="B.iam")
        s1.items.append(_make_drawing_item())
        assert s2.items == []


class TestCreationItemResult:
    def test_success(self):
        item = _make_drawing_item()
        result = CreationItemResult(
            item=item,
            success=True,
            action="revision_only",
            duration_seconds=2.3,
        )
        assert result.success is True
        assert result.action == "revision_only"
        assert result.error_message is None
        assert result.duration_seconds == 2.3

    def test_failure(self):
        item = _make_drawing_item()
        result = CreationItemResult(
            item=item,
            success=False,
            action="created+revision",
            error_message="COM error: drawing not found",
            duration_seconds=0.5,
        )
        assert result.success is False
        assert result.error_message == "COM error: drawing not found"

    def test_defaults(self):
        item = _make_drawing_item()
        result = CreationItemResult(item=item, success=True)
        assert result.action == ""
        assert result.error_message is None
        assert result.duration_seconds == 0.0

    def test_skipped_action(self):
        item = _make_drawing_item(include=False)
        result = CreationItemResult(item=item, success=True, action="skipped")
        assert result.action == "skipped"

    def test_item_reference(self):
        item = _make_drawing_item()
        result = CreationItemResult(item=item, success=True)
        assert result.item is item


class TestCreationSummary:
    def test_defaults(self):
        s = CreationSummary()
        assert s.total == 0
        assert s.created == 0
        assert s.revised == 0
        assert s.failed == 0
        assert s.results == []

    def test_construction(self):
        item = _make_drawing_item()
        r = CreationItemResult(item=item, success=True, action="revision_only")
        s = CreationSummary(total=3, created=1, revised=2, failed=0, results=[r])
        assert s.total == 3
        assert s.created == 1
        assert s.revised == 2
        assert s.failed == 0
        assert len(s.results) == 1

    def test_results_list_not_shared(self):
        s1 = CreationSummary()
        s2 = CreationSummary()
        s1.results.append(CreationItemResult(item=_make_drawing_item(), success=True))
        assert s2.results == []
