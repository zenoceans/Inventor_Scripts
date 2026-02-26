"""Tests for pure conversion functions in inventor_export_tool.settings_dialog."""

from inventor_export_tool.settings_dialog import (
    AP_PROTOCOLS,
    SHEET_RANGES,
    ap_protocol_to_int,
    ap_protocol_to_label,
    build_export_options,
    parse_export_options,
    sheet_range_to_int,
    sheet_range_to_label,
)


# ---------------------------------------------------------------------------
# AP protocol conversions
# ---------------------------------------------------------------------------


class TestApProtocolConstants:
    def test_ap203_value(self):
        assert AP_PROTOCOLS["AP 203"] == 2

    def test_ap214_value(self):
        assert AP_PROTOCOLS["AP 214"] == 3


class TestApProtocolToLabel:
    def test_2_returns_ap203(self):
        assert ap_protocol_to_label(2) == "AP 203"

    def test_3_returns_ap214(self):
        assert ap_protocol_to_label(3) == "AP 214"

    def test_unknown_falls_back_to_ap214(self):
        assert ap_protocol_to_label(99) == "AP 214"

    def test_zero_falls_back_to_ap214(self):
        assert ap_protocol_to_label(0) == "AP 214"


class TestApProtocolToInt:
    def test_ap203_returns_2(self):
        assert ap_protocol_to_int("AP 203") == 2

    def test_ap214_returns_3(self):
        assert ap_protocol_to_int("AP 214") == 3

    def test_unknown_falls_back_to_3(self):
        assert ap_protocol_to_int("AP 999") == 3

    def test_empty_string_falls_back_to_3(self):
        assert ap_protocol_to_int("") == 3


# ---------------------------------------------------------------------------
# Sheet range conversions
# ---------------------------------------------------------------------------


class TestSheetRangeConstants:
    def test_all_sheets_value(self):
        assert SHEET_RANGES["All Sheets"] == 0

    def test_custom_range_value(self):
        assert SHEET_RANGES["Custom Range"] == 1

    def test_current_sheet_value(self):
        assert SHEET_RANGES["Current Sheet"] == 2


class TestSheetRangeToLabel:
    def test_0_returns_all_sheets(self):
        assert sheet_range_to_label(0) == "All Sheets"

    def test_1_returns_custom_range(self):
        assert sheet_range_to_label(1) == "Custom Range"

    def test_2_returns_current_sheet(self):
        assert sheet_range_to_label(2) == "Current Sheet"

    def test_unknown_falls_back_to_all_sheets(self):
        assert sheet_range_to_label(99) == "All Sheets"

    def test_negative_falls_back_to_all_sheets(self):
        assert sheet_range_to_label(-1) == "All Sheets"


class TestSheetRangeToInt:
    def test_all_sheets_returns_0(self):
        assert sheet_range_to_int("All Sheets") == 0

    def test_custom_range_returns_1(self):
        assert sheet_range_to_int("Custom Range") == 1

    def test_current_sheet_returns_2(self):
        assert sheet_range_to_int("Current Sheet") == 2

    def test_unknown_falls_back_to_0(self):
        assert sheet_range_to_int("Some Other Value") == 0

    def test_empty_string_falls_back_to_0(self):
        assert sheet_range_to_int("") == 0


# ---------------------------------------------------------------------------
# build_export_options
# ---------------------------------------------------------------------------


class TestBuildExportOptions:
    def test_all_populated(self):
        step = {"ApplicationProtocolType": 3}
        pdf = {"Vector_Resolution": 600}
        dwg = {"Export_Acad_IniFile": "acad.ini"}
        result = build_export_options(step, pdf, dwg)
        assert result == {"step": step, "pdf": pdf, "dwg": dwg}

    def test_omits_empty_step(self):
        pdf = {"Vector_Resolution": 400}
        dwg = {"Export_Acad_IniFile": "acad.ini"}
        result = build_export_options({}, pdf, dwg)
        assert "step" not in result
        assert result["pdf"] == pdf
        assert result["dwg"] == dwg

    def test_omits_empty_pdf(self):
        step = {"ApplicationProtocolType": 2}
        dwg = {"Export_Acad_IniFile": "acad.ini"}
        result = build_export_options(step, {}, dwg)
        assert "pdf" not in result
        assert result["step"] == step
        assert result["dwg"] == dwg

    def test_omits_empty_dwg(self):
        step = {"ApplicationProtocolType": 3}
        pdf = {"All_Color_AS_Black": True}
        result = build_export_options(step, pdf, {})
        assert "dwg" not in result
        assert result["step"] == step
        assert result["pdf"] == pdf

    def test_all_empty_returns_empty_dict(self):
        result = build_export_options({}, {}, {})
        assert result == {}

    def test_only_step_populated(self):
        step = {"ApplicationProtocolType": 3, "Author": "Jane"}
        result = build_export_options(step, {}, {})
        assert result == {"step": step}


# ---------------------------------------------------------------------------
# parse_export_options
# ---------------------------------------------------------------------------


class TestParseExportOptions:
    def test_full_dict_extracts_all(self):
        step = {"ApplicationProtocolType": 3}
        pdf = {"Vector_Resolution": 600}
        dwg = {"Export_Acad_IniFile": "acad.ini"}
        s, p, d = parse_export_options({"step": step, "pdf": pdf, "dwg": dwg})
        assert s == step
        assert p == pdf
        assert d == dwg

    def test_missing_step_defaults_to_empty(self):
        pdf = {"Vector_Resolution": 400}
        s, p, d = parse_export_options({"pdf": pdf})
        assert s == {}
        assert p == pdf
        assert d == {}

    def test_missing_pdf_defaults_to_empty(self):
        step = {"ApplicationProtocolType": 2}
        s, p, d = parse_export_options({"step": step})
        assert p == {}

    def test_missing_dwg_defaults_to_empty(self):
        s, p, d = parse_export_options({"step": {}, "pdf": {}})
        assert d == {}

    def test_empty_dict_returns_three_empty_dicts(self):
        s, p, d = parse_export_options({})
        assert s == {}
        assert p == {}
        assert d == {}


# ---------------------------------------------------------------------------
# Roundtrip tests
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_build_then_parse(self):
        step = {"ApplicationProtocolType": 2, "Author": "Alice"}
        pdf = {"Vector_Resolution": 300, "All_Color_AS_Black": True}
        dwg = {"Export_Acad_IniFile": r"C:\acad.ini"}
        built = build_export_options(step, pdf, dwg)
        s, p, d = parse_export_options(built)
        assert s == step
        assert p == pdf
        assert d == dwg

    def test_build_then_parse_with_empty_dwg(self):
        step = {"ApplicationProtocolType": 3}
        pdf = {"Sheet_Range": 1, "Custom_Begin_Sheet": 2, "Custom_End_Sheet": 5}
        built = build_export_options(step, pdf, {})
        s, p, d = parse_export_options(built)
        assert s == step
        assert p == pdf
        assert d == {}

    def test_parse_then_build_preserves_content(self):
        original = {
            "step": {"ApplicationProtocolType": 2},
            "pdf": {"Vector_Resolution": 600},
        }
        s, p, d = parse_export_options(original)
        rebuilt = build_export_options(s, p, d)
        assert rebuilt == original

    def test_parse_then_build_empty(self):
        s, p, d = parse_export_options({})
        rebuilt = build_export_options(s, p, d)
        assert rebuilt == {}

    def test_ap_protocol_label_int_roundtrip(self):
        for label in AP_PROTOCOLS:
            assert ap_protocol_to_label(ap_protocol_to_int(label)) == label

    def test_sheet_range_label_int_roundtrip(self):
        for label in SHEET_RANGES:
            assert sheet_range_to_label(sheet_range_to_int(label)) == label
