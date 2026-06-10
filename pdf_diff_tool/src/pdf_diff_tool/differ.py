"""Core PDF diff algorithm using anaglyph overlay."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import fitz
import numpy as np
from PIL import Image

from pdf_diff_tool.models import DiffResult

ProgressCallback = Callable[[int, int], None]


def _render_page(page: fitz.Page, dpi: int) -> np.ndarray:
    """Render a PDF page to a grayscale NumPy array."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return img


def _normalize_sizes(old: np.ndarray, new: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pad arrays with white (255) so they have the same dimensions."""
    max_h = max(old.shape[0], new.shape[0])
    max_w = max(old.shape[1], new.shape[1])

    def _pad(arr: np.ndarray) -> np.ndarray:
        if arr.shape[0] == max_h and arr.shape[1] == max_w:
            return arr
        padded = np.full((max_h, max_w), 255, dtype=np.uint8)
        padded[: arr.shape[0], : arr.shape[1]] = arr
        return padded

    return _pad(old), _pad(new)


def diff_pdfs(
    old_path: Path,
    new_path: Path,
    output_path: Path,
    dpi: int = 150,
    progress_callback: ProgressCallback | None = None,
) -> DiffResult:
    """Compare two PDFs and write an anaglyph diff PDF.

    Args:
        old_path: Path to the old (previous revision) PDF.
        new_path: Path to the new (current revision) PDF.
        output_path: Where to save the diff PDF.
        dpi: Render resolution (default 150).
        progress_callback: Optional ``(current, total)`` progress reporter.

    Returns:
        DiffResult with output path, page count, and whether differences exist.
    """
    old_doc = fitz.open(str(old_path))
    new_doc = fitz.open(str(new_path))

    max_pages = max(len(old_doc), len(new_doc))
    has_differences = False
    diff_images: list[Image.Image] = []

    for i in range(max_pages):
        if progress_callback:
            progress_callback(i + 1, max_pages)

        if i < len(old_doc):
            old_gray = _render_page(old_doc[i], dpi)
        else:
            # Page only in new doc — render new page size as white
            new_pix = new_doc[i].get_pixmap(
                matrix=fitz.Matrix(dpi / 72, dpi / 72), colorspace=fitz.csGRAY
            )
            old_gray = np.full((new_pix.height, new_pix.width), 255, dtype=np.uint8)

        if i < len(new_doc):
            new_gray = _render_page(new_doc[i], dpi)
        else:
            # Page only in old doc — render old page size as white
            new_gray = np.full_like(old_gray, 255)

        # Normalize sizes once, reuse for both anaglyph and comparison
        old_norm, new_norm = _normalize_sizes(old_gray, new_gray)

        if not np.array_equal(old_norm, new_norm):
            has_differences = True

        # Build RGB anaglyph: old in red channel, new in green+blue
        # Result: unchanged → gray, removed → magenta, added → green/cyan
        rgb = np.stack([old_norm, new_norm, new_norm], axis=2)
        diff_images.append(Image.fromarray(rgb, mode="RGB"))

    old_doc.close()
    new_doc.close()

    # Save all diff pages as a single PDF
    if diff_images:
        diff_images[0].save(
            str(output_path),
            "PDF",
            save_all=True,
            append_images=diff_images[1:] if len(diff_images) > 1 else [],
            resolution=dpi,
        )
        # Also emit per-page PNGs alongside the PDF so the anaglyph pages can be
        # opened by image viewers/tools that cannot parse PIL's image-only PDF.
        for page_index, image in enumerate(diff_images, start=1):
            image.save(str(output_path.with_name(f"{output_path.stem}_p{page_index}.png")))

    return DiffResult(
        output_path=output_path,
        page_count=max_pages,
        has_differences=has_differences,
    )
