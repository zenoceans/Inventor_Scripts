"""Tests for inventor_drawing_tool.scanner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from inventor_api.document import AssemblyDocument, InventorDocument
from inventor_api.traversal import DiscoveredComponent
from inventor_drawing_tool.config import DrawingConfig
from inventor_drawing_tool.models import DrawingStatus
from inventor_drawing_tool.scanner import scan_assembly_for_release


def _make_config(**overrides) -> DrawingConfig:
    config = DrawingConfig()
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


def _make_part_doc(full_path: str) -> InventorDocument:
    doc = MagicMock(spec=InventorDocument)
    doc.full_path = full_path
    doc.display_name = full_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return doc


def _make_assembly_doc(full_path: str) -> AssemblyDocument:
    doc = MagicMock(spec=AssemblyDocument)
    doc.full_path = full_path
    doc.display_name = full_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return doc


def _make_app(assembly_path: str = r"C:\Projects\Assembly.iam") -> MagicMock:
    app = MagicMock()
    asm = _make_assembly_doc(assembly_path)
    app.get_active_assembly.return_value = asm
    return app


class TestScanAssemblyForRelease:
    def test_basic_scan(self, tmp_path):
        """ScanResult totals reflect the discovered components."""
        part1 = str(tmp_path / "Bracket.ipt")
        part2 = str(tmp_path / "Plate.ipt")
        # Create Bracket.idw on disk so find_idw_path returns it
        (tmp_path / "Bracket.idw").write_text("")

        app = _make_app(str(tmp_path / "Assembly.iam"))
        comps = [
            DiscoveredComponent(document=_make_part_doc(part1), is_top_level=False, depth=1),
            DiscoveredComponent(document=_make_part_doc(part2), is_top_level=False, depth=1),
        ]

        with patch("inventor_drawing_tool.scanner.walk_assembly", return_value=comps):
            result = scan_assembly_for_release(app, _make_config())

        assert result.total_parts == 2
        assert result.parts_with_drawings == 1
        assert result.parts_without_drawings == 1
        assert len(result.items) == 2

    def test_skips_top_level(self):
        """Root assembly (is_top_level=True) is excluded from items."""
        asm_doc = _make_assembly_doc(r"C:\Projects\Assembly.iam")
        app = MagicMock()
        app.get_active_assembly.return_value = asm_doc

        comps = [
            DiscoveredComponent(document=asm_doc, is_top_level=True, depth=0),
            DiscoveredComponent(
                document=_make_part_doc(r"C:\Projects\Bracket.ipt"),
                is_top_level=False,
                depth=1,
            ),
        ]

        with patch("inventor_drawing_tool.scanner.walk_assembly", return_value=comps):
            with patch("inventor_drawing_tool.scanner.find_idw_path", return_value=None):
                result = scan_assembly_for_release(app, _make_config())

        # Only 1 item — the top-level was skipped
        assert result.total_parts == 1
        assert result.items[0].part_path == r"C:\Projects\Bracket.ipt"

    def test_existing_drawing_detected(self, tmp_path):
        """DrawingStatus.EXISTING when the .idw file is present on disk."""
        ipt = tmp_path / "Bracket.ipt"
        idw = tmp_path / "Bracket.idw"
        ipt.write_text("")
        idw.write_text("")

        app = _make_app(str(tmp_path / "Assembly.iam"))
        comps = [
            DiscoveredComponent(document=_make_part_doc(str(ipt)), is_top_level=False, depth=1)
        ]

        with patch("inventor_drawing_tool.scanner.walk_assembly", return_value=comps):
            result = scan_assembly_for_release(app, _make_config())

        assert result.items[0].drawing_status == DrawingStatus.EXISTING
        assert result.items[0].drawing_path == str(idw)

    def test_missing_drawing_detected(self, tmp_path):
        """DrawingStatus.NEEDS_CREATION when no .idw file exists."""
        ipt = tmp_path / "Bracket.ipt"
        ipt.write_text("")

        app = _make_app(str(tmp_path / "Assembly.iam"))
        comps = [
            DiscoveredComponent(document=_make_part_doc(str(ipt)), is_top_level=False, depth=1)
        ]

        with patch("inventor_drawing_tool.scanner.walk_assembly", return_value=comps):
            result = scan_assembly_for_release(app, _make_config())

        assert result.items[0].drawing_status == DrawingStatus.NEEDS_CREATION
        assert result.items[0].drawing_path is None

    def test_document_type_detection(self):
        """AssemblyDocument yields document_type='assembly'; InventorDocument yields 'part'."""
        asm_doc = _make_assembly_doc(r"C:\Projects\Sub.iam")
        part_doc = _make_part_doc(r"C:\Projects\Bracket.ipt")

        app = _make_app()
        comps = [
            DiscoveredComponent(document=asm_doc, is_top_level=False, depth=1),
            DiscoveredComponent(document=part_doc, is_top_level=False, depth=1),
        ]

        with patch("inventor_drawing_tool.scanner.walk_assembly", return_value=comps):
            with patch("inventor_drawing_tool.scanner.find_idw_path", return_value=None):
                result = scan_assembly_for_release(app, _make_config())

        assert result.items[0].document_type == "assembly"
        assert result.items[1].document_type == "part"

    def test_depth_passed_through(self):
        """The depth from DiscoveredComponent is carried into DrawingItem.depth."""
        part_doc = _make_part_doc(r"C:\Projects\Deep\Bracket.ipt")

        app = _make_app()
        comps = [
            DiscoveredComponent(document=part_doc, is_top_level=False, depth=3),
        ]

        with patch("inventor_drawing_tool.scanner.walk_assembly", return_value=comps):
            with patch("inventor_drawing_tool.scanner.find_idw_path", return_value=None):
                result = scan_assembly_for_release(app, _make_config())

        assert result.items[0].depth == 3

    def test_config_params_passed_to_walk(self):
        """walk_assembly is called with the correct parameters from config."""
        config = _make_config(
            include_suppressed=True,
            include_content_center=True,
            max_depth=2,
            include_parts=True,
            include_subassemblies=False,
        )
        app = _make_app()

        with patch("inventor_drawing_tool.scanner.walk_assembly", return_value=[]) as mock_walk:
            scan_assembly_for_release(app, config)

        mock_walk.assert_called_once_with(
            app.get_active_assembly.return_value,
            include_suppressed=True,
            include_content_center=True,
            max_depth=2,
            include_parts=True,
            include_assemblies=False,
        )
