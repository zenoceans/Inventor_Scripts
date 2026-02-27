"""Datasheet PDF download and weight extraction."""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

import httpx

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None  # type: ignore[assignment]

_log = logging.getLogger(__name__)

# Regex patterns for weight/mass in datasheets
_WEIGHT_PATTERN = re.compile(
    r"(?:weight|mass|gewicht|net\s*weight|unit\s*weight)"
    r"[:\s]*"
    r"(\d+[.,]?\d*)\s*"
    r"(mg|g|kg|oz|lb|lbs)",
    re.IGNORECASE,
)

_UNIT_TO_GRAMS: dict[str, float] = {
    "mg": 0.001,
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.3495,
    "lb": 453.592,
    "lbs": 453.592,
}


def download_datasheet(url: str, dest_dir: Path) -> Path | None:
    """Download a PDF datasheet. Returns the saved file path, or None on failure."""
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                _log.warning("Datasheet download failed: %s -> %s", url, resp.status_code)
                return None

            # Determine filename from URL or use generic name
            filename = url.rsplit("/", 1)[-1] if "/" in url else "datasheet.pdf"
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"

            dest = dest_dir / filename
            dest.write_bytes(resp.content)
            return dest
    except Exception:
        _log.warning("Datasheet download error: %s", url, exc_info=True)
        return None


def extract_weight_from_pdf(pdf_path: Path) -> float | None:
    """Extract weight from a PDF datasheet using text search.

    Searches all pages for weight/mass patterns and returns the value in grams.
    Returns None if no weight found.
    """
    try:
        doc = pymupdf.open(str(pdf_path))
        for page in doc:
            text = page.get_text()
            match = _WEIGHT_PATTERN.search(text)
            if match:
                value_str = match.group(1).replace(",", ".")
                unit = match.group(2).lower()
                value = float(value_str)
                grams = value * _UNIT_TO_GRAMS[unit]
                doc.close()
                return round(grams, 4)
        doc.close()
    except Exception:
        _log.warning("PDF weight extraction error: %s", pdf_path, exc_info=True)
    return None


def lookup_weight_from_datasheet(url: str, tmp_dir: Path | None = None) -> float | None:
    """Download a datasheet PDF and try to extract weight.

    Convenience wrapper combining download + extraction.
    Returns weight in grams, or None if not found or on any error.
    """
    if tmp_dir is None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="vendor_api_"))

    pdf_path = download_datasheet(url, tmp_dir)
    if pdf_path is None:
        return None

    return extract_weight_from_pdf(pdf_path)
