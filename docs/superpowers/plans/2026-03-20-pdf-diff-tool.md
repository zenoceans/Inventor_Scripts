# PDF Diff Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PDF Diff tab to Zabra-Cadabra that compares two PDF files using an anaglyph algorithm and outputs a diff PDF with magenta (removed) and green (added) highlighting.

**Architecture:** New workspace package `pdf_diff_tool` with PyMuPDF + Pillow + NumPy. Core diff logic in `differ.py`, GUI tab in `gui.py`, CLI in `cli.py`. Follows existing tool package pattern (config dataclass, queue-based threading, TabSpec registration).

**Tech Stack:** PyMuPDF (fitz), Pillow, NumPy, tkinter/ttk

**Spec:** `docs/superpowers/specs/2026-03-19-pdf-diff-tool-design.md`

---

## File Structure

### New files (package: `pdf_diff_tool/`)

| File | Responsibility |
|------|---------------|
| `pdf_diff_tool/pyproject.toml` | Package metadata, dependencies (pymupdf, Pillow, numpy), CLI entry point |
| `pdf_diff_tool/src/pdf_diff_tool/__init__.py` | Empty package init |
| `pdf_diff_tool/src/pdf_diff_tool/__main__.py` | `python -m pdf_diff_tool` entry, calls `cli.main()` |
| `pdf_diff_tool/src/pdf_diff_tool/models.py` | `DiffResult` dataclass |
| `pdf_diff_tool/src/pdf_diff_tool/differ.py` | Core anaglyph diff algorithm |
| `pdf_diff_tool/src/pdf_diff_tool/config.py` | `PdfDiffConfig` dataclass + load/save |
| `pdf_diff_tool/src/pdf_diff_tool/cli.py` | argparse CLI: `pdf-diff old.pdf new.pdf` |
| `pdf_diff_tool/src/pdf_diff_tool/gui.py` | ttk.Frame tab for Zabra-Cadabra |
| `pdf_diff_tool/tests/conftest.py` | Test fixtures (synthetic PDF helper) |
| `pdf_diff_tool/tests/test_differ.py` | Differ algorithm tests |
| `pdf_diff_tool/tests/test_config.py` | Config round-trip tests |

### Modified files

| File | Change |
|------|--------|
| `pyproject.toml` (root) | Add `"pdf_diff_tool"` to workspace members |
| `zabra_cadabra/pyproject.toml` | Add `"pdf-diff-tool"` to dependencies + uv sources |
| `zabra_cadabra/src/zabra_cadabra/tab_registry.py` | Add `_make_pdf_diff_tab()` factory + `TabSpec` |
| `zabra_cadabra/src/zabra_cadabra/app.py` | Add config load/save for pdf_diff |

---

## Task 1: Package Scaffolding

**Files:**
- Create: `pdf_diff_tool/pyproject.toml`
- Create: `pdf_diff_tool/src/pdf_diff_tool/__init__.py`
- Create: `pdf_diff_tool/src/pdf_diff_tool/__main__.py`
- Create: `pdf_diff_tool/tests/__init__.py`
- Modify: `pyproject.toml` (root, line 8-17)

- [ ] **Step 1: Create `pdf_diff_tool/pyproject.toml`**

```toml
[project]
name = "pdf-diff-tool"
version = "0.1.0"
description = "Visual PDF comparison tool using anaglyph overlay"
requires-python = ">=3.10"
dependencies = ["pymupdf>=1.24", "Pillow>=10.0", "numpy>=1.26", "inventor-utils"]

[project.scripts]
pdf-diff = "pdf_diff_tool.cli:main"

[tool.uv.sources]
inventor-utils = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `pdf_diff_tool/src/pdf_diff_tool/__init__.py`**

```python
```

(Empty file)

- [ ] **Step 3: Create `pdf_diff_tool/src/pdf_diff_tool/__main__.py`**

```python
"""Allow ``python -m pdf_diff_tool``."""

from pdf_diff_tool.cli import main

main()
```

- [ ] **Step 4: Add to root workspace**

In `pyproject.toml` (root), add `"pdf_diff_tool"` to the `members` list:

```toml
[tool.uv.workspace]
members = [
    "inventor_api",
    "inventor_utils",
    "inventor_export_tool",
    "inventor_simplify_tool",
    "inventor_drawing_tool",
    "vendor_api_tool",
    "wattius_commissioning_tool",
    "zabra_cadabra",
    "pdf_diff_tool",
]
```

- [ ] **Step 5: Create `pdf_diff_tool/tests/__init__.py`**

(Empty file)

- [ ] **Step 6: Run `uv sync --all-packages`**

Run: `uv sync --all-packages`
Expected: Installs pymupdf, Pillow, numpy, inventor-utils. No errors.

- [ ] **Step 7: Commit**

```bash
git add pdf_diff_tool/pyproject.toml pdf_diff_tool/src/pdf_diff_tool/__init__.py pdf_diff_tool/src/pdf_diff_tool/__main__.py pdf_diff_tool/tests/__init__.py pyproject.toml
git commit -m "feat(pdf-diff): scaffold pdf_diff_tool package"
```

---

## Task 2: Models

**Files:**
- Create: `pdf_diff_tool/src/pdf_diff_tool/models.py`

- [ ] **Step 1: Create `models.py`**

```python
"""Data models for PDF diff results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiffResult:
    """Result of comparing two PDFs."""

    output_path: Path
    page_count: int
    has_differences: bool
```

- [ ] **Step 2: Commit**

```bash
git add pdf_diff_tool/src/pdf_diff_tool/models.py
git commit -m "feat(pdf-diff): add DiffResult model"
```

---

## Task 3: Core Diff Algorithm — Tests First

**Files:**
- Create: `pdf_diff_tool/tests/conftest.py`
- Create: `pdf_diff_tool/tests/test_differ.py`

- [ ] **Step 1: Create `conftest.py` with synthetic PDF helper**

```python
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
```

- [ ] **Step 2: Create `test_differ.py` with all test cases**

```python
"""Tests for the core PDF diff algorithm."""

from __future__ import annotations

import numpy as np
from pathlib import Path

from pdf_diff_tool.differ import diff_pdfs


class TestDiffPdfs:
    """Test the diff_pdfs function."""

    def test_identical_pdfs_no_differences(self, make_pdf, tmp_path: Path):
        """Identical PDFs should produce a result with has_differences=False."""
        pdf_a = make_pdf("a.pdf", texts=["Hello World"])
        pdf_b = make_pdf("b.pdf", texts=["Hello World"])
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert not result.has_differences
        assert result.page_count == 1
        assert result.output_path == output
        assert output.exists()

    def test_added_content_detected(self, make_pdf, tmp_path: Path):
        """New content in the new PDF should be detected as differences."""
        pdf_a = make_pdf("a.pdf", texts=["Hello"])
        pdf_b = make_pdf("b.pdf", texts=["Hello", "World"])
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.has_differences

    def test_removed_content_detected(self, make_pdf, tmp_path: Path):
        """Content removed from the new PDF should be detected."""
        pdf_a = make_pdf("a.pdf", texts=["Hello", "World"])
        pdf_b = make_pdf("b.pdf", texts=["Hello"])
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.has_differences

    def test_graphical_change_detected(self, make_pdf, tmp_path: Path):
        """Changes in drawn shapes should be detected."""
        pdf_a = make_pdf("a.pdf", rects=[(50, 50, 200, 200)])
        pdf_b = make_pdf("b.pdf", rects=[(100, 100, 300, 300)])
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.has_differences

    def test_page_count_mismatch_extra_new(self, make_pdf, tmp_path: Path):
        """When new PDF has more pages, diff should cover all pages."""
        pdf_a = make_pdf("a.pdf", texts=["Page 1"])
        # Create a 2-page PDF manually
        import fitz
        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((72, 72), "Page 1", fontsize=14)
        p2 = doc.new_page(width=595, height=842)
        p2.insert_text((72, 72), "Page 2", fontsize=14)
        pdf_b = tmp_path / "b.pdf"
        doc.save(str(pdf_b))
        doc.close()

        output = tmp_path / "diff.pdf"
        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.page_count == 2
        assert result.has_differences

    def test_different_page_sizes_handled(self, make_pdf, tmp_path: Path):
        """PDFs with different page sizes should not crash."""
        pdf_a = make_pdf("a.pdf", texts=["Small"], page_width=400, page_height=600)
        pdf_b = make_pdf("b.pdf", texts=["Large"], page_width=595, page_height=842)
        output = tmp_path / "diff.pdf"

        result = diff_pdfs(pdf_a, pdf_b, output)

        assert result.output_path == output
        assert output.exists()

    def test_output_pdf_is_valid(self, make_pdf, tmp_path: Path):
        """The output diff PDF should be openable by PyMuPDF."""
        import fitz
        pdf_a = make_pdf("a.pdf", texts=["A"])
        pdf_b = make_pdf("b.pdf", texts=["B"])
        output = tmp_path / "diff.pdf"

        diff_pdfs(pdf_a, pdf_b, output)

        doc = fitz.open(str(output))
        assert len(doc) == 1
        doc.close()
```

- [ ] **Step 3: Run tests — verify they fail**

Run: `cd pdf_diff_tool && uv run --package pdf-diff-tool pytest tests/test_differ.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pdf_diff_tool.differ'`

- [ ] **Step 4: Commit test files**

```bash
git add pdf_diff_tool/tests/conftest.py pdf_diff_tool/tests/test_differ.py
git commit -m "test(pdf-diff): add differ tests (red phase)"
```

---

## Task 4: Core Diff Algorithm — Implementation

**Files:**
- Create: `pdf_diff_tool/src/pdf_diff_tool/differ.py`

- [ ] **Step 1: Implement `differ.py`**

```python
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

    return DiffResult(
        output_path=output_path,
        page_count=max_pages,
        has_differences=has_differences,
    )
```

- [ ] **Step 2: Run tests — verify they pass**

Run: `cd pdf_diff_tool && uv run --package pdf-diff-tool pytest tests/test_differ.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add pdf_diff_tool/src/pdf_diff_tool/differ.py
git commit -m "feat(pdf-diff): implement anaglyph diff algorithm"
```

---

## Task 5: Config

**Files:**
- Create: `pdf_diff_tool/src/pdf_diff_tool/config.py`
- Create: `pdf_diff_tool/tests/test_config.py`

- [ ] **Step 1: Create `test_config.py`**

```python
"""Tests for PDF diff config loading and saving."""

from __future__ import annotations

from pathlib import Path

from pdf_diff_tool.config import PdfDiffConfig, load_config, save_config


class TestPdfDiffConfig:
    def test_defaults(self):
        config = PdfDiffConfig()
        assert config.dpi == 150
        assert config.open_after_diff is True
        assert config.last_old_path == ""
        assert config.last_new_path == ""

    def test_round_trip(self, tmp_path: Path):
        path = tmp_path / "test_config.json"
        original = PdfDiffConfig(dpi=300, open_after_diff=False, last_old_path="a.pdf")
        save_config(original, path)
        loaded = load_config(path)
        assert loaded.dpi == 300
        assert loaded.open_after_diff is False
        assert loaded.last_old_path == "a.pdf"

    def test_load_missing_file_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        config = load_config(path)
        assert config.dpi == 150
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd pdf_diff_tool && uv run --package pdf-diff-tool pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pdf_diff_tool.config'`

- [ ] **Step 3: Create `config.py`**

```python
"""Load and save PDF Diff tool preferences as JSON."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from inventor_utils.config import get_config_path, load_dataclass_config, save_dataclass_config


@dataclass
class PdfDiffConfig:
    """User-configurable settings for the PDF Diff tool."""

    dpi: int = 150
    open_after_diff: bool = True
    last_old_path: str = ""
    last_new_path: str = ""


def load_config(path: Path | None = None) -> PdfDiffConfig:
    """Load PdfDiffConfig from JSON file. Returns defaults if missing or corrupt."""
    if path is None:
        path = get_config_path("pdf_diff_config.json")
    return load_dataclass_config(PdfDiffConfig, path)


def save_config(config: PdfDiffConfig, path: Path | None = None) -> None:
    """Save PdfDiffConfig to JSON file."""
    if path is None:
        path = get_config_path("pdf_diff_config.json")
    save_dataclass_config(config, path)
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd pdf_diff_tool && uv run --package pdf-diff-tool pytest tests/test_config.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_diff_tool/src/pdf_diff_tool/config.py pdf_diff_tool/tests/test_config.py pdf_diff_tool/pyproject.toml
git commit -m "feat(pdf-diff): add PdfDiffConfig with load/save"
```

---

## Task 6: CLI

**Files:**
- Create: `pdf_diff_tool/src/pdf_diff_tool/cli.py`

- [ ] **Step 1: Create `cli.py`**

```python
"""CLI entry point for pdf_diff_tool."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pdf_diff_tool.config import load_config
from pdf_diff_tool.differ import diff_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two PDF files and generate a visual diff PDF."
    )
    parser.add_argument("old_pdf", type=Path, help="Path to the old (previous revision) PDF")
    parser.add_argument("new_pdf", type=Path, help="Path to the new (current revision) PDF")
    parser.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="Output path for the diff PDF (default: alongside new PDF)",
    )
    parser.add_argument(
        "--dpi", type=int, default=None, help="Render resolution in DPI (default: 150)"
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Don't open the diff PDF after generation"
    )
    args = parser.parse_args()

    if not args.old_pdf.exists():
        print(f"Error: file not found: {args.old_pdf}", file=sys.stderr)
        sys.exit(1)
    if not args.new_pdf.exists():
        print(f"Error: file not found: {args.new_pdf}", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    dpi = args.dpi or config.dpi

    if args.output:
        output_path = args.output
    else:
        output_path = args.new_pdf.parent / f"{args.old_pdf.stem}_vs_{args.new_pdf.stem}_diff.pdf"

    def log_progress(current: int, total: int) -> None:
        print(f"Processing page {current}/{total}...")

    try:
        result = diff_pdfs(args.old_pdf, args.new_pdf, output_path, dpi=dpi, progress_callback=log_progress)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if result.has_differences:
        print(f"Differences found. Diff saved to: {result.output_path}")
    else:
        print(f"No differences found. Diff saved to: {result.output_path}")

    if not args.no_open and config.open_after_diff:
        os.startfile(str(result.output_path))
```

- [ ] **Step 2: Verify CLI runs**

Run: `uv run pdf-diff --help`
Expected: Shows help text with old_pdf, new_pdf, --output, --dpi, --no-open options.

- [ ] **Step 3: Commit**

```bash
git add pdf_diff_tool/src/pdf_diff_tool/cli.py
git commit -m "feat(pdf-diff): add CLI entry point"
```

---

## Task 7: GUI Tab

**Files:**
- Create: `pdf_diff_tool/src/pdf_diff_tool/gui.py`

- [ ] **Step 1: Create `gui.py`**

```python
"""PDF Diff tab — compare two PDF files and produce an anaglyph diff PDF."""

from __future__ import annotations

import logging
import os
import queue
import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf_diff_tool.config import PdfDiffConfig

logger = logging.getLogger(__name__)


class PdfDiffGUI(ttk.Frame):
    """PDF visual diff tab content."""

    POLL_INTERVAL_MS = 100

    def __init__(self, parent: tk.Widget, config: PdfDiffConfig | None = None) -> None:
        super().__init__(parent)
        from pdf_diff_tool.config import PdfDiffConfig as _C

        self._config = config or _C()
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker_thread: Thread | None = None

        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # --- File selection ---
        file_frame = ttk.LabelFrame(self, text="PDF Files", padding=8)
        file_frame.pack(fill="x", **pad)
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="Old PDF:").grid(row=0, column=0, sticky="w", pady=2)
        self._old_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self._old_path_var, width=60).grid(
            row=0, column=1, sticky="ew", padx=(4, 4), pady=2
        )
        ttk.Button(file_frame, text="Browse...", command=self._browse_old).grid(
            row=0, column=2, pady=2
        )

        ttk.Label(file_frame, text="New PDF:").grid(row=1, column=0, sticky="w", pady=2)
        self._new_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self._new_path_var, width=60).grid(
            row=1, column=1, sticky="ew", padx=(4, 4), pady=2
        )
        ttk.Button(file_frame, text="Browse...", command=self._browse_new).grid(
            row=1, column=2, pady=2
        )

        # --- Settings ---
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill="x", **pad)

        ttk.Label(settings_frame, text="DPI:").pack(side="left")
        self._dpi_var = tk.IntVar(value=150)
        dpi_spin = ttk.Spinbox(
            settings_frame, from_=72, to=600, textvariable=self._dpi_var, width=6
        )
        dpi_spin.pack(side="left", padx=(4, 16))

        self._open_after_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, text="Open after comparison", variable=self._open_after_var
        ).pack(side="left")

        # --- Action button ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", **pad)

        self._compare_btn = ttk.Button(btn_frame, text="Compare", command=self._on_compare)
        self._compare_btn.pack(side="left")

        # --- Log area ---
        log_frame = ttk.LabelFrame(self, text="Log", padding=4)
        log_frame.pack(fill="both", expand=True, **pad)

        self._log_text = tk.Text(
            log_frame,
            height=8,
            state="disabled",
            wrap="word",
            bg="#f5f5f5",
            fg="#000000",
            insertbackground="#000000",
            selectbackground="#000000",
            selectforeground="#ffffff",
            font=("Consolas", 9),
        )
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        # --- Progress bar ---
        prog_frame = ttk.Frame(self)
        prog_frame.pack(fill="x", **pad)

        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(
            prog_frame, variable=self._progress_var, maximum=100
        )
        self._progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._progress_label = ttk.Label(prog_frame, text="Ready")
        self._progress_label.pack(side="right")

    # ------------------------------------------------------------------
    # File browsing
    # ------------------------------------------------------------------

    def _browse_old(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Old PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if path:
            self._old_path_var.set(path)

    def _browse_new(self) -> None:
        path = filedialog.askopenfilename(
            title="Select New PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if path:
            self._new_path_var.set(path)

    # ------------------------------------------------------------------
    # Config load / save
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        self._old_path_var.set(self._config.last_old_path)
        self._new_path_var.set(self._config.last_new_path)
        self._dpi_var.set(self._config.dpi)
        self._open_after_var.set(self._config.open_after_diff)

    def _save_config(self) -> None:
        self._config.last_old_path = self._old_path_var.get()
        self._config.last_new_path = self._new_path_var.get()
        self._config.dpi = self._dpi_var.get()
        self._config.open_after_diff = self._open_after_var.get()

    # ------------------------------------------------------------------
    # Queue-based thread communication
    # ------------------------------------------------------------------

    def _process_queue(self) -> None:
        try:
            while True:
                msg_type, data = self._queue.get_nowait()
                if msg_type == "log":
                    self._append_log(data)
                elif msg_type == "progress":
                    current, total = data
                    if total > 0:
                        pct = (current / total) * 100
                        self._progress_var.set(pct)
                        self._progress_label.configure(text=f"{current}/{total} ({pct:.0f}%)")
                elif msg_type == "done":
                    result = data
                    if result.has_differences:
                        self._append_log(f"Differences found. Saved: {result.output_path.name}")
                    else:
                        self._append_log(
                            f"No differences found. Saved: {result.output_path.name}"
                        )
                    self._on_worker_done()
                    if self._open_after_var.get():
                        os.startfile(str(result.output_path))
                elif msg_type == "error":
                    self._append_log(f"ERROR: {data}")
                    self._on_worker_done()
        except queue.Empty:
            pass
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def _append_log(self, message: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _set_working(self, working: bool) -> None:
        self._compare_btn.configure(state="disabled" if working else "normal")

    def _on_worker_done(self) -> None:
        self._set_working(False)
        self._worker_thread = None

    def _on_compare(self) -> None:
        old_path = self._old_path_var.get().strip()
        new_path = self._new_path_var.get().strip()

        if not old_path or not new_path:
            self._append_log("Please select both old and new PDF files.")
            return
        if not Path(old_path).exists():
            self._append_log(f"Old PDF not found: {old_path}")
            return
        if not Path(new_path).exists():
            self._append_log(f"New PDF not found: {new_path}")
            return

        self._save_config()
        self._set_working(True)
        self._progress_var.set(0)
        self._progress_label.configure(text="Starting...")

        self._worker_thread = Thread(
            target=self._run_worker, args=(old_path, new_path), daemon=True
        )
        self._worker_thread.start()

    def _run_worker(self, old_path: str, new_path: str) -> None:
        from pdf_diff_tool.differ import diff_pdfs

        old = Path(old_path)
        new = Path(new_path)
        output = new.parent / f"{old.stem}_vs_{new.stem}_diff.pdf"

        def progress_cb(current: int, total: int) -> None:
            self._queue.put(("progress", (current, total)))

        def log_cb(msg: str) -> None:
            self._queue.put(("log", msg))

        try:
            log_cb(f"Comparing: {old.name} vs {new.name}")
            result = diff_pdfs(old, new, output, dpi=self._config.dpi, progress_callback=progress_cb)
            self._queue.put(("done", result))
        except Exception as e:
            logger.exception("Diff worker failed")
            self._queue.put(("error", str(e)))

    # ------------------------------------------------------------------
    # Shell interface
    # ------------------------------------------------------------------

    def start_polling(self) -> None:
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def close(self) -> None:
        self._save_config()
```

- [ ] **Step 2: Commit**

```bash
git add pdf_diff_tool/src/pdf_diff_tool/gui.py
git commit -m "feat(pdf-diff): add GUI tab"
```

---

## Task 8: Zabra-Cadabra Integration

**Files:**
- Modify: `zabra_cadabra/pyproject.toml` (lines 6-12, 17-22)
- Modify: `zabra_cadabra/src/zabra_cadabra/tab_registry.py` (lines 55-88)
- Modify: `zabra_cadabra/src/zabra_cadabra/app.py` (lines 13-75)

- [ ] **Step 1: Add dependency to `zabra_cadabra/pyproject.toml`**

Add `"pdf-diff-tool"` to the `dependencies` list and add the workspace source:

```toml
dependencies = [
    "inventor-export-tool",
    "inventor-simplify-tool",
    "inventor-drawing-tool",
    "vendor-api-tool",
    "wattius-commissioning-tool",
    "pdf-diff-tool",
]

[tool.uv.sources]
inventor-export-tool = { workspace = true }
inventor-simplify-tool = { workspace = true }
inventor-drawing-tool = { workspace = true }
vendor-api-tool = { workspace = true }
wattius-commissioning-tool = { workspace = true }
pdf-diff-tool = { workspace = true }
```

- [ ] **Step 2: Add TabSpec to `tab_registry.py`**

Add the factory function and TabSpec entry. Add the factory function before the `TABS` list:

```python
def _make_pdf_diff_tab(parent: tk.Widget, config: Any) -> ttk.Frame:
    from pdf_diff_tool.gui import PdfDiffGUI

    return PdfDiffGUI(parent, config)
```

Add to `TABS` list:

```python
    TabSpec(
        title="PDF Diff",
        factory=_make_pdf_diff_tab,
        config_key="pdf_diff",
    ),
```

- [ ] **Step 3: Add config loading/saving to `app.py`**

Add import (after existing config imports, around line 17):

```python
    from pdf_diff_tool.config import load_config as load_pdf_diff_config
    from pdf_diff_tool.config import save_config as save_pdf_diff_config
```

Add config loading (after `commissioning_config = ...`, around line 33):

```python
    pdf_diff_config = load_pdf_diff_config()
```

Add to the configs dict (before `"show_prototype_tabs"`):

```python
            "pdf_diff": pdf_diff_config,
```

Add save in the finally block (after `save_commissioning_config(...)`, around line 74):

```python
        save_pdf_diff_config(pdf_diff_config)
```

- [ ] **Step 4: Run `uv sync --all-packages`**

Run: `uv sync --all-packages`
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add zabra_cadabra/pyproject.toml zabra_cadabra/src/zabra_cadabra/tab_registry.py zabra_cadabra/src/zabra_cadabra/app.py
git commit -m "feat(pdf-diff): integrate PDF Diff tab into Zabra-Cadabra"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Run all pdf_diff_tool tests**

Run: `uv run --package pdf-diff-tool pytest -v`
Expected: All tests pass (7 differ + 3 config = 10 tests).

- [ ] **Step 2: Run ruff check and format**

Run: `uv run ruff check pdf_diff_tool/`
Run: `uv run ruff format pdf_diff_tool/`
Expected: No errors. Fix any issues.

- [ ] **Step 3: Verify CLI help**

Run: `uv run pdf-diff --help`
Expected: Shows usage with old_pdf, new_pdf, --output, --dpi, --no-open.

- [ ] **Step 4: Commit any lint fixes**

If ruff made changes:
```bash
git add -u
git commit -m "style(pdf-diff): apply ruff formatting"
```
