# PDF Diff Tool — Design Spec

## Context

When reviewing engineering drawing revisions, there is no easy way to see exactly what changed between two PDF versions. Drawings contain both graphical content (views, dimensions, annotations) and text (title blocks, BOMs, revision tables). A visual diff tool that highlights pixel-level changes makes revision review faster and more reliable.

## Scope

A new Zabra-Cadabra tab (`pdf_diff_tool`) that compares two PDF files and produces an overlay diff PDF highlighting what changed. Single file comparison only (no batch mode).

## Approach

**Pure Python** using PyMuPDF (fitz) + Pillow + NumPy. No external executables.

### Algorithm (per page)

1. **Render** both pages to grayscale images at configurable DPI (default 150)
2. **Normalize** — pad the shorter/narrower page with white to match dimensions
3. **Compute anaglyph** — place old page in red channel, new page in green+blue channels
   - Unchanged pixels → gray
   - Removed pixels (old only) → magenta
   - Added pixels (new only) → green/cyan
4. **Compose output** — save all diff pages as a single multi-page PDF
5. **Handle page count mismatch** — if one PDF has more pages, show extra pages as fully added/removed

### Output

- **Format:** Single PDF file, one overlay diff page per compared page
- **Location:** Same directory as the new PDF
- **Naming:** `<old_stem>_vs_<new_stem>_diff.pdf`
- **Auto-open:** Configurable option to open the diff PDF in the default viewer after comparison

## Package Structure

```
pdf_diff_tool/
├── pyproject.toml
├── src/pdf_diff_tool/
│   ├── __init__.py
│   ├── __main__.py          # calls cli.main()
│   ├── cli.py               # argparse entry point: pdf-diff old.pdf new.pdf
│   ├── config.py            # PdfDiffConfig dataclass + load/save
│   ├── gui.py               # ttk.Frame tab for Zabra-Cadabra
│   ├── differ.py            # Core diff algorithm (render + compare + output)
│   └── models.py            # DiffResult dataclass
└── tests/
    ├── conftest.py
    ├── test_differ.py
    └── test_config.py
```

Note: No `orchestrator.py` — this tool doesn't use COM/Inventor, so `BaseOrchestrator` doesn't apply. The diff logic lives in `differ.py` and runs on a background thread directly from `gui.py`.

## Dependencies

- `pymupdf` (fitz) — PDF rendering and output PDF creation
- `Pillow` — image manipulation
- `numpy` — pixel-level array operations

## Config (`PdfDiffConfig`)

```python
@dataclass
class PdfDiffConfig:
    dpi: int = 150
    open_after_diff: bool = True
    last_old_path: str = ""
    last_new_path: str = ""
```

## GUI Layout (Single File Mode)

```
┌─────────────────────────────────────────────────┐
│  Old PDF:  [________________________] [Browse]  │
│  New PDF:  [________________________] [Browse]  │
│                                                 │
│  DPI: [150]    ☑ Open after comparison          │
│                                                 │
│  [▶ Compare]                                    │
│                                                 │
│  Log:                                           │
│  ┌─────────────────────────────────────────────┐│
│  │ Rendering page 1/3 ...                      ││
│  │ Computing diff page 1/3 ...                 ││
│  │ ✓ Saved: Part-001_vs_Part-001-RevB_diff.pdf ││
│  └─────────────────────────────────────────────┘│
│  [████████████████████░░░░░░░░░]  67%           │
└─────────────────────────────────────────────────┘
```

Follows the existing Zabra-Cadabra black-and-white theme. Uses queue-based threading pattern for progress updates (same as other tabs).

## CLI

```
pdf-diff old.pdf new.pdf [--output path] [--dpi 150] [--no-open]
```

- `old.pdf` — the previous revision
- `new.pdf` — the current revision
- `--output` — override output path (default: same dir as new.pdf)
- `--dpi` — render resolution (default: 150)
- `--no-open` — skip opening the result

## Integration Details

- **Tab title:** "PDF Diff"
- **Config key:** `pdf_diff`
- **Config file:** `pdf_diff_config.json`
- **Prototype:** `False` (no COM dependency, low risk — ship visible immediately)

### Files to modify

- `pyproject.toml` (root) — add `pdf_diff_tool` to workspace members
- `zabra_cadabra/pyproject.toml` — add `pdf_diff_tool` as dependency
- `zabra_cadabra/src/zabra_cadabra/tab_registry.py` — add `TabSpec` for PDF Diff
- `zabra_cadabra/src/zabra_cadabra/app.py` — add config loading/saving

### New files

- Entire `pdf_diff_tool/` package (see structure above)

## Testing

- **`test_differ.py`** — test the core diff algorithm with small synthetic PDFs created via PyMuPDF (no fixtures needed). Test cases:
  - Identical PDFs → all-gray output
  - Added content → green pixels present
  - Removed content → magenta pixels present
  - Page count mismatch handling
  - Different page sizes
- **`test_config.py`** — load/save round-trip

### Verification

```bash
uv sync --all-packages
uv run --package pdf_diff_tool pytest        # Unit tests
uv run pdf-diff old.pdf new.pdf              # CLI smoke test
uv run zabra-cadabra                         # Verify tab appears and works
uv run ruff check .                          # Lint
uv run ruff format .                         # Format
```

## Non-Goals (Future)

- Batch/folder mode (compare all PDFs in two folders)
- Text-aware diffing (extract text from title blocks)
- In-app preview of diff result
- Configurable colors for added/removed
