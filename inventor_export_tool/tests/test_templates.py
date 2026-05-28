"""Tests for inventor_export_tool.templates."""

from __future__ import annotations

from unittest.mock import MagicMock

from inventor_export_tool.templates import BUILTIN_TOKENS, render_template


def _make_doc(props: dict[str, str | None], full_path: str = r"C:\Parts\Bracket.ipt") -> MagicMock:
    """Build a minimal InventorDocument mock for template tests."""
    doc = MagicMock()
    doc.full_path = full_path

    def get_iproperty(name: str) -> str | None:
        for k, v in props.items():
            if k.lower() == name.lower():
                return v if v else None
        return None

    doc.get_iproperty = MagicMock(side_effect=get_iproperty)
    return doc


class TestRenderTemplate:
    def test_single_token_renders(self):
        doc = _make_doc({"Part Number": "BRK-001"})
        result = render_template("{Part Number}", doc, fallback_filename="fallback")
        assert result == "BRK-001"

    def test_multi_token_renders(self):
        doc = _make_doc({"Part Number": "BRK-001", "Revision Number": "B"})
        result = render_template(
            "{Part Number} - Rev{Revision Number}", doc, fallback_filename="f"
        )
        assert result == "BRK-001 - RevB"

    def test_filename_token_returns_file_stem(self):
        doc = _make_doc({}, full_path=r"C:\Projects\MyPart.ipt")
        result = render_template("{filename}", doc, fallback_filename="fallback")
        assert result == "MyPart"

    def test_filename_token_case_insensitive(self):
        doc = _make_doc({}, full_path=r"C:\Projects\MyPart.ipt")
        assert render_template("{FILENAME}", doc, fallback_filename="f") == "MyPart"
        assert render_template("{Filename}", doc, fallback_filename="f") == "MyPart"

    def test_missing_token_renders_empty_and_collapses_whitespace(self):
        """{Part Number} - {Description} - Rev with missing Description -> 'BRK-001 - - Rev'"""
        doc = _make_doc({"Part Number": "BRK-001", "Description": None})
        result = render_template(
            "{Part Number} - {Description} - Rev", doc, fallback_filename="fallback"
        )
        # raw rendered: "BRK-001 -  - Rev"
        # sanitize_filename: unchanged
        # collapse whitespace: "BRK-001 - - Rev"
        # strip " -": "BRK-001 - - Rev" (no leading/trailing dash)
        assert result == "BRK-001 - - Rev"

    def test_all_missing_tokens_returns_fallback(self):
        doc = _make_doc({})
        result = render_template(
            "{Part Number} - {Description}", doc, fallback_filename="Fallback"
        )
        assert result == "Fallback"

    def test_invalid_chars_in_property_value_are_sanitized(self):
        doc = _make_doc({"Part Number": "BRK/001:2"})
        result = render_template("{Part Number}", doc, fallback_filename="fallback")
        # sanitize_filename replaces / and : with _
        assert "/" not in result
        assert ":" not in result
        assert "BRK" in result

    def test_custom_user_defined_property_renders(self):
        doc = _make_doc({"My Custom Prop": "CustomValue"})
        result = render_template("{My Custom Prop}", doc, fallback_filename="fallback")
        assert result == "CustomValue"

    def test_case_insensitive_token_lookup(self):
        doc = _make_doc({"Part Number": "BRK-001"})
        assert render_template("{PART NUMBER}", doc, fallback_filename="f") == "BRK-001"
        assert render_template("{part number}", doc, fallback_filename="f") == "BRK-001"

    def test_empty_template_returns_fallback(self):
        doc = _make_doc({})
        result = render_template("", doc, fallback_filename="MyFallback")
        assert result == "MyFallback"

    def test_literal_text_with_no_tokens(self):
        doc = _make_doc({})
        result = render_template("StaticName", doc, fallback_filename="fallback")
        assert result == "StaticName"

    def test_leading_trailing_dash_stripped(self):
        doc = _make_doc({"Part Number": None})
        result = render_template("{Part Number} - Suffix", doc, fallback_filename="fallback")
        # "{Part Number}" renders empty -> " - Suffix" -> strip leading " -" -> "Suffix"
        assert result == "Suffix"

    def test_whitespace_collapsed(self):
        doc = _make_doc({"Part Number": "P1", "Description": "  "})
        # Description is whitespace-only -> treated as None -> rendered empty
        result = render_template("{Part Number}  {Description}  End", doc, fallback_filename="f")
        # "P1    End" -> collapse -> "P1 End"
        assert result == "P1 End"


class TestBuiltinTokens:
    def test_is_list_of_strings(self):
        assert isinstance(BUILTIN_TOKENS, list)
        assert all(isinstance(t, str) for t in BUILTIN_TOKENS)

    def test_contains_expected_tokens(self):
        assert "Part Number" in BUILTIN_TOKENS
        assert "Description" in BUILTIN_TOKENS
        assert "Revision Number" in BUILTIN_TOKENS
        assert "filename" in BUILTIN_TOKENS
