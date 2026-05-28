"""Tests for orchestrator._build_export_items with template-based naming."""

from __future__ import annotations

from unittest.mock import MagicMock

from inventor_export_tool.config import AppConfig, NamingPreset
from inventor_export_tool.models import ComponentInfo
from inventor_export_tool.orchestrator import _build_export_items


def _make_component(
    display_name: str = "Bracket",
    source_path: str = r"C:\Parts\Bracket.ipt",
    document_type: str = "part",
    revision: str = "A",
    is_top_level: bool = False,
    idw_path: str | None = None,
) -> ComponentInfo:
    return ComponentInfo(
        source_path=source_path,
        display_name=display_name,
        document_type=document_type,
        revision=revision,
        is_top_level=is_top_level,
        idw_path=idw_path,
    )


def _make_doc(
    part_number: str = "BRK-001", description: str = "Bracket", revision: str = "A"
) -> MagicMock:
    doc = MagicMock()
    doc.full_path = r"C:\Parts\Bracket.ipt"
    props = {
        "part number": part_number,
        "description": description,
        "revision number": revision,
    }
    doc.get_iproperty = MagicMock(side_effect=lambda name: props.get(name.lower()))
    return doc


class TestBuildExportItems:
    def _config_with_preset(self, template: str) -> AppConfig:
        preset = NamingPreset(name="Test", template=template)
        return AppConfig(
            export_step=True,
            export_dwg=False,
            export_pdf=False,
            naming_presets=[preset],
            active_preset_name="Test",
        )

    def test_step_filename_uses_template(self):
        comp = _make_component()
        doc = _make_doc(part_number="BRK-001", description="Bracket", revision="B")
        doc_cache = {r"C:\Parts\Bracket.ipt": doc}
        config = self._config_with_preset("{Part Number} - {Description} - Rev{Revision Number}")
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        assert len(items) == 1
        assert items[0].output_filename == "BRK-001 - Bracket - RevB.step"

    def test_missing_token_falls_back_to_display_name(self):
        comp = _make_component(display_name="Bracket")
        doc = _make_doc(part_number="", description="", revision="")
        doc_cache = {r"C:\Parts\Bracket.ipt": doc}
        config = self._config_with_preset("{Part Number}")
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        # render_template returns fallback_filename when all tokens empty
        assert items[0].output_filename == "Bracket.step"

    def test_dwg_and_pdf_use_same_base_name(self):
        idw = r"C:\Parts\Bracket.idw"
        comp = _make_component(idw_path=idw)
        doc = _make_doc(part_number="BRK-001", description="Bracket", revision="A")
        doc_cache = {r"C:\Parts\Bracket.ipt": doc}
        config = AppConfig(
            export_step=False,
            export_dwg=True,
            export_pdf=True,
            naming_presets=[NamingPreset("T", "{Part Number}")],
            active_preset_name="T",
        )
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        names = [i.output_filename for i in items]
        assert "BRK-001.dwg" in names
        assert "BRK-001.pdf" in names

    def test_filters_parts_when_include_parts_false(self):
        comp = _make_component(document_type="part")
        doc_cache = {r"C:\Parts\Bracket.ipt": _make_doc()}
        config = AppConfig(
            export_step=True,
            include_parts=False,
            naming_presets=[NamingPreset("T", "{Part Number}")],
            active_preset_name="T",
        )
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        assert items == []

    def test_output_path_uses_output_folder(self):
        comp = _make_component()
        doc_cache = {r"C:\Parts\Bracket.ipt": _make_doc(part_number="BRK-001")}
        config = self._config_with_preset("{Part Number}")
        items = _build_export_items([comp], config, r"C:\exports", doc_cache)
        assert items[0].output_path.startswith(r"C:\exports")
