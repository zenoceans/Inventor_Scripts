# Inventor Batch Export Tool

## Project Overview

Two-package Python project:
1. **`inventor_api/`** — Reusable, library-grade Pythonic wrapper around Autodesk Inventor 2026 COM API. Designed to be extractable as a standalone library.
2. **`inventor_export_tool/`** — Tkinter desktop app that uses `inventor_api` to batch-export STEP/DWG/PDF from assemblies.

See `ARCHITECTURE.md` for design, `COM-API-REFERENCE.md` for raw COM API, `Export_Plan.md` for task breakdown.

## Dev Toolchain

- **Package manager:** `uv` (not pip). Use `uv add`, `uv sync`, `uv run`.
- **Python:** >=3.10, targeting 3.13
- **Linting:** `ruff check` and `ruff format` — run before declaring any task done
- **Type checking:** `ty check` (not mypy)
- **Testing:** `pytest` — run with `uv run pytest`
- **Platform:** Windows 11 only (COM automation via pywin32)

## Project Structure

```
inventor_api/                  # Reusable Inventor COM wrapper
  __init__.py                  # Public exports
  application.py               # InventorApp — connect, lifecycle
  document.py                  # Document wrappers (Part, Assembly, Drawing)
  properties.py                # iProperty access
  traversal.py                 # Assembly tree walking
  exporters.py                 # STEP/DWG/PDF export
  types.py                     # Enums, constants
  exceptions.py                # Custom exceptions
  _com_threading.py            # COM thread init helper

inventor_export_tool/          # Application
  __init__.py
  __main__.py                  # Entry point
  app.py                       # Init + launches GUI
  gui.py                       # Tkinter GUI
  models.py                    # ExportItem, ScanSummary, ExportResult
  naming.py                    # Filename composition, IDW finding
  config.py                    # JSON config persistence
  export_log.py                # Export logging
  orchestrator.py              # Scan + export logic

tests/
  conftest.py                  # Mock COM factories
  test_naming.py
  test_models.py
  test_config.py
  test_export_log.py
  inventor_api/
    test_types.py
    test_document.py
    test_traversal.py
    test_exporters.py
```

## Key Conventions

### inventor_api Rules
- **Library-grade code** — no app-specific logic, no GUI references
- **Dependency injection** — all classes accept COM object in constructor, enabling mock testing
- **Custom exceptions** — never let raw `pywintypes.com_error` escape; wrap in `InventorError` subclasses
- **Every public class/function must have tests** using mock COM objects
- Docstrings on all public API (this is a library)

### Testing Rules
- **Unit tests required for all pure functions** and all inventor_api public API
- Tests mirror module paths: `tests/test_naming.py`, `tests/inventor_api/test_document.py`
- Use `tmp_path` for file I/O tests
- Use `unittest.mock.MagicMock` for COM objects — configure with expected attributes
- Mock factories live in `tests/conftest.py`

### Code Style
- Type hints on all public function signatures
- Use `dataclass` for structured data, not dicts
- Use `Enum`/`IntEnum` for constants, not magic numbers
- No docstrings on private/internal functions unless non-obvious

### Architecture Boundary
- **`inventor_api`**: Pythonic COM wrapper. Returns its own types. No imports from `inventor_export_tool`.
- **`inventor_export_tool`**: App logic. Imports from `inventor_api`. Contains GUI, config, naming, orchestration.
- **GUI** (`gui.py`): No direct COM or inventor_api calls — goes through `orchestrator.py` on background thread.

### API Documentation
- All `inventor_api` public API documented in README.md
- When adding/changing public functions, update README

## MCP Servers

- **memory** — Search before exploring source files. Store non-obvious insights after tasks.
- **ide** — `getDiagnostics` for type errors. `executeCode` for Jupyter experiments.

## Common Commands

```bash
uv sync                                # Install dependencies
uv run python -m inventor_export_tool  # Run the app
uv run pytest                          # Run all tests
uv run pytest tests/inventor_api/      # Run inventor_api tests only
uv run ruff check .                    # Lint
uv run ruff format .                   # Format
uv run ty check                        # Type check
```
