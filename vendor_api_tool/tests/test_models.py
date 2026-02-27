"""Tests for vendor_api_tool.models."""

from __future__ import annotations

from vendor_api_tool.models import ComponentResult


class TestComponentResult:
    def test_creation_with_required_fields(self):
        result = ComponentResult(source="nexar", mpn="LM358")
        assert result.source == "nexar"
        assert result.mpn == "LM358"
        assert result.manufacturer == ""
        assert result.description == ""
        assert result.weight_grams is None
        assert result.datasheet_url == ""
        assert result.product_url == ""
        assert result.raw_specs == {}

    def test_creation_with_all_fields(self):
        result = ComponentResult(
            source="digikey",
            mpn="NE555P",
            manufacturer="Texas Instruments",
            description="IC OSC SGL TIMER 100KHZ 8DIP",
            weight_grams=0.5,
            datasheet_url="https://example.com/ne555p.pdf",
            product_url="https://digikey.com/ne555p",
            raw_specs={"supply_voltage": "5-15V", "package": "DIP-8"},
        )
        assert result.source == "digikey"
        assert result.mpn == "NE555P"
        assert result.manufacturer == "Texas Instruments"
        assert result.description == "IC OSC SGL TIMER 100KHZ 8DIP"
        assert result.weight_grams == 0.5
        assert result.datasheet_url == "https://example.com/ne555p.pdf"
        assert result.product_url == "https://digikey.com/ne555p"
        assert result.raw_specs == {"supply_voltage": "5-15V", "package": "DIP-8"}

    def test_equality(self):
        a = ComponentResult(source="pdf", mpn="ABC123", manufacturer="Acme")
        b = ComponentResult(source="pdf", mpn="ABC123", manufacturer="Acme")
        assert a == b

    def test_inequality_different_mpn(self):
        a = ComponentResult(source="nexar", mpn="ABC")
        b = ComponentResult(source="nexar", mpn="XYZ")
        assert a != b

    def test_raw_specs_default_is_independent(self):
        a = ComponentResult(source="nexar", mpn="A")
        b = ComponentResult(source="nexar", mpn="B")
        a.raw_specs["key"] = "value"
        assert b.raw_specs == {}
