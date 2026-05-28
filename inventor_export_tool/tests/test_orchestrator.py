"""Tests for orchestrator._build_export_items with template-based naming."""

from __future__ import annotations

from unittest.mock import MagicMock

from inventor_export_tool.config import AppConfig, NamingPreset
from inventor_export_tool.models import ComponentInfo
from inventor_export_tool.orchestrator import (
    _build_export_items,
    _matches_excluded_prefix,
    _normalize_prefixes,
)


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


class TestExcludedFilenamePrefixes:
    def test_normalize_strips_and_lowercases(self):
        assert _normalize_prefixes(["  DIN ", "ISO", "", "  "]) == ["din", "iso"]

    def test_normalize_empty_list(self):
        assert _normalize_prefixes([]) == []

    def test_matcher_case_insensitive(self):
        assert _matches_excluded_prefix("din-912-bolt", ["din"]) is True
        assert _matches_excluded_prefix("DIN-912-BOLT", ["din"]) is True
        assert _matches_excluded_prefix("BRK-001", ["din"]) is False

    def test_matcher_returns_false_for_empty_prefix_list(self):
        assert _matches_excluded_prefix("DIN-912", []) is False

    def test_matcher_any_prefix_matches(self):
        prefixes = ["din", "iso", "2"]
        assert _matches_excluded_prefix("ISO-4014-Pin", prefixes) is True
        assert _matches_excluded_prefix("234-Pipe", prefixes) is True
        assert _matches_excluded_prefix("BRK-001", prefixes) is False

    def test_build_filters_by_prefix(self):
        bolt = _make_component(display_name="DIN-912-Bolt", source_path=r"C:\Parts\DIN-912.ipt")
        pin = _make_component(display_name="ISO-4014-Pin", source_path=r"C:\Parts\ISO-4014.ipt")
        bracket = _make_component(
            display_name="BRK-001-Bracket", source_path=r"C:\Parts\BRK-001.ipt"
        )
        doc_cache = {
            r"C:\Parts\DIN-912.ipt": _make_doc(part_number="DIN-912"),
            r"C:\Parts\ISO-4014.ipt": _make_doc(part_number="ISO-4014"),
            r"C:\Parts\BRK-001.ipt": _make_doc(part_number="BRK-001"),
        }
        config = AppConfig(
            export_step=True,
            export_dwg=False,
            export_pdf=False,
            excluded_filename_prefixes=["DIN", "ISO"],
            naming_presets=[NamingPreset("T", "{Part Number}")],
            active_preset_name="T",
        )
        items = _build_export_items([bolt, pin, bracket], config, r"C:\out", doc_cache)
        assert [i.output_filename for i in items] == ["BRK-001.step"]

    def test_build_prefix_matching_case_insensitive(self):
        comp = _make_component(display_name="din-912", source_path=r"C:\P\din-912.ipt")
        doc_cache = {r"C:\P\din-912.ipt": _make_doc(part_number="din-912")}
        config = AppConfig(
            export_step=True,
            excluded_filename_prefixes=["DIN"],
            naming_presets=[NamingPreset("T", "{Part Number}")],
            active_preset_name="T",
        )
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        assert items == []

    def test_build_empty_excluded_prefixes_excludes_nothing(self):
        comp = _make_component(display_name="DIN-912", source_path=r"C:\P\DIN.ipt")
        doc_cache = {r"C:\P\DIN.ipt": _make_doc(part_number="DIN-912")}
        config = AppConfig(
            export_step=True,
            excluded_filename_prefixes=[],
            naming_presets=[NamingPreset("T", "{Part Number}")],
            active_preset_name="T",
        )
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        assert len(items) == 1

    def test_build_whitespace_only_prefix_ignored(self):
        comp = _make_component(display_name="ABC", source_path=r"C:\P\ABC.ipt")
        doc_cache = {r"C:\P\ABC.ipt": _make_doc(part_number="ABC")}
        config = AppConfig(
            export_step=True,
            excluded_filename_prefixes=["   ", ""],
            naming_presets=[NamingPreset("T", "{Part Number}")],
            active_preset_name="T",
        )
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        assert len(items) == 1
