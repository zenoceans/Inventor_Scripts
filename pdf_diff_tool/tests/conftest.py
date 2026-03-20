"""Test fixtures for pdf_diff_tool."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest


@pytest.fixture
def make_pdf(tmp_path: Path):
    """Factory fixture: create a single-page PDF with given text and/or rectangles.

    Usage:
        pdf_path = make_pdf("hello.pdf", texts=["Hello"], rects=[(50, 50, 200, 200)])
    """

    def _make(
        filename: str,
        texts: list[str] | None = None,
        rects: list[tuple[float, float, float, float]] | None = None,
        page_width: float = 595,
        page_height: float = 842,
    ) -> Path:
        doc = fitz.open()
        page = doc.new_page(width=page_width, height=page_height)
        y = 72
        for text in texts or []:
            page.insert_text((72, y), text, fontsize=14)
            y += 20
        for rect in rects or []:
            page.draw_rect(fitz.Rect(*rect), color=(0, 0, 0), width=2)
        path = tmp_path / filename
        doc.save(str(path))
        doc.close()
        return path

    return _make
