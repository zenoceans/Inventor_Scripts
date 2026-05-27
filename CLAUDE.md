# Zabra-Cadabra

## Project Overview

Six-package uv workspace for Autodesk Inventor 2026 automation tools:

1. **`zabra_cadabra/`** — Multi-tab Tkinter shell app. Black-and-white themed. Entry point for the .exe.
2. **`inventor_api/`** — Reusable Pythonic wrapper around Inventor COM API. Designed as a standalone library.
3. **`inventor_export_tool/`** — Batch export (STEP/DWG/PDF). CLI: `inventor-export`.
4. **`inventor_simplify_tool/`** — Simplify/shrinkwrap tool. CLI: `inventor-simplify`.
5. **`inventor_drawing_tool/`** — Batch drawing creation. CLI: `inventor-drawing`.
6. **`inventor_utils/`** — Shared utilities (filenames, config, base logger, base orchestrator).

Each tool has a `gui.py` (`ttk.Frame` tab embedded in Zabra-Cadabra) and a `cli.py` (standalone argparse entry point).

See `ARCHITECTURE.md` for design, `COM-API-REFERENCE.md` for raw COM API.

## Dev Toolchain

- **Package manager:** `uv` (not pip)
- **Python:** >=3.10, targeting 3.13
- **Platform:** Windows 11 only (COM automation via pywin32)
- **Layout:** uv workspace with `src/` layout per package

## Code Style

- Type hints on all public function signatures
- Use `dataclass` for structured data, not dicts
- Use `Enum`/`IntEnum` for constants, not magic numbers
- No docstrings on private/internal functions unless non-obvious

## Adding a New Tab

1. Create package dir with `pyproject.toml` and `src/<name>/` using src layout.
2. Add as workspace member in root `pyproject.toml`.
3. Create `gui.py` with `ttk.Frame` subclass (accepts `parent` and optional `config`).
4. Create `cli.py` with argparse `main()`. Create `__main__.py` calling `cli.main()`.
5. Add as dependency of `zabra_cadabra` in `zabra_cadabra/pyproject.toml`.
6. Add `TabSpec` in `zabra_cadabra/src/zabra_cadabra/tab_registry.py`.
7. If config needed, add loader in `zabra_cadabra/src/zabra_cadabra/app.py`, pass via `configs` dict.

## Common Commands

```bash
uv sync --all-packages                          # Install all workspace packages
uv run zabra-cadabra                            # Run the full GUI app
uv run inventor-export --help                   # Export tool CLI
uv run inventor-simplify --help                 # Simplify tool CLI
uv run inventor-drawing --help                  # Drawing tool CLI
uv run --package inventor-api pytest            # Test inventor_api
uv run --package inventor-export-tool pytest    # Test inventor_export_tool
uv run --package inventor-simplify-tool pytest  # Test inventor_simplify_tool
uv run --package inventor-drawing-tool pytest   # Test inventor_drawing_tool
uv run --package inventor-utils pytest          # Test inventor_utils
uv run --package zabra-cadabra pytest           # Test zabra_cadabra
uv run ruff check .                             # Lint
uv run ruff format .                            # Format
uv run ty check                                 # Type check
cd zabra_cadabra && uv run python build.py      # Build .exe
```
