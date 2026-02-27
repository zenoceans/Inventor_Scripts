"""Data models for vendor API results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ComponentResult:
    """Result from a vendor API or datasheet lookup."""

    source: str  # "nexar", "digikey", "pdf"
    mpn: str
    manufacturer: str = ""
    description: str = ""
    weight_grams: float | None = None
    datasheet_url: str = ""
    product_url: str = ""
    raw_specs: dict[str, str] = field(default_factory=dict)
