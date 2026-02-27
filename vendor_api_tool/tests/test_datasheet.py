"""Tests for datasheet PDF download and weight extraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from vendor_api_tool.datasheet import download_datasheet, extract_weight_from_pdf


def _make_mock_doc(text: str) -> MagicMock:
    page = MagicMock()
    page.get_text.return_value = text
    doc = MagicMock()
    doc.__iter__ = MagicMock(return_value=iter([page]))
    return doc


def test_extract_weight_grams(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF fake")

    mock_doc = _make_mock_doc("Weight: 1.5 g")

    with patch("vendor_api_tool.datasheet.pymupdf") as mock_pymupdf:
        mock_pymupdf.open.return_value = mock_doc
        result = extract_weight_from_pdf(pdf_path)

    assert result == 1.5


def test_extract_weight_milligrams(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF fake")

    mock_doc = _make_mock_doc("Mass: 150 mg")

    with patch("vendor_api_tool.datasheet.pymupdf") as mock_pymupdf:
        mock_pymupdf.open.return_value = mock_doc
        result = extract_weight_from_pdf(pdf_path)

    assert result == 0.15


def test_extract_weight_kilograms(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF fake")

    mock_doc = _make_mock_doc("Net weight: 0.8 kg")

    with patch("vendor_api_tool.datasheet.pymupdf") as mock_pymupdf:
        mock_pymupdf.open.return_value = mock_doc
        result = extract_weight_from_pdf(pdf_path)

    assert result == 800.0


def test_extract_weight_european_decimal(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF fake")

    mock_doc = _make_mock_doc("Gewicht: 15,3 g")

    with patch("vendor_api_tool.datasheet.pymupdf") as mock_pymupdf:
        mock_pymupdf.open.return_value = mock_doc
        result = extract_weight_from_pdf(pdf_path)

    assert result == 15.3


def test_extract_weight_not_found(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF fake")

    mock_doc = _make_mock_doc("Operating voltage: 3.3V, current: 100mA")

    with patch("vendor_api_tool.datasheet.pymupdf") as mock_pymupdf:
        mock_pymupdf.open.return_value = mock_doc
        result = extract_weight_from_pdf(pdf_path)

    assert result is None


def test_download_datasheet_success(tmp_path: Path) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"%PDF-1.4 fake content"

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.get.return_value = mock_resp

    with patch("vendor_api_tool.datasheet.httpx.Client", return_value=mock_client_instance):
        result = download_datasheet("https://example.com/component.pdf", tmp_path)

    assert result is not None
    assert result == tmp_path / "component.pdf"
    assert result.read_bytes() == b"%PDF-1.4 fake content"


def test_download_datasheet_failure(tmp_path: Path) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_instance.get.return_value = mock_resp

    with patch("vendor_api_tool.datasheet.httpx.Client", return_value=mock_client_instance):
        result = download_datasheet("https://example.com/missing.pdf", tmp_path)

    assert result is None
