# Zabra-Cadabra

## Project Overview

Six-package uv workspace Python project:
1. **`zabra_cadabra/`** — Multi-tab Tkinter shell application ("Zabra-Cadabra"). Black-and-white themed with Zen logo. Each tool/script is a tab. Entry point for the .exe.
2. **`inventor_api/`** — Reusable, library-grade Pythonic wrapper around Autodesk Inventor 2026 COM API. Designed to be extractable as a standalone library.
3. **`inventor_export_tool/`** — Inventor batch-export tool (STEP/DWG/PDF). CLI-standalone via `inventor-export`. Its GUI (`ExportToolGUI`) is a `ttk.Frame` tab embedded in Zabra-Cadabra.
4. **`inventor_simplify_tool/`** — Inventor simplify/shrinkwrap tool. CLI-standalone via `inventor-simplify`. Its GUI is a `ttk.Frame` tab embedded in Zabra-Cadabra.
5. **`inventor_drawing_tool/`** — Inventor batch drawing creation and revision release tool. CLI-standalone via `inventor-drawing`. Its GUI (`DrawingToolGUI`) is a `ttk.Frame` tab embedded in Zabra-Cadabra.
6. **`inventor_utils/`** — Shared utilities (filenames, config helpers, base logger, base orchestrator) used across tool packages.

See `ARCHITECTURE.md` for design, `COM-API-REFERENCE.md` for raw COM API, `Export_Plan.md` for task breakdown.

## Dev Toolchain

- **Package manager:** `uv` (not pip). Use `uv add`, `uv sync --all-packages`, `uv run`.
- **Python:** >=3.10, targeting 3.13
- **Linting:** `ruff check` and `ruff format` — run before declaring any task done
- **Type checking:** `ty check` (not mypy)
- **Testing:** `pytest` — run per-package with `uv run --package <name> pytest`
- **Platform:** Windows 11 only (COM automation via pywin32)

## Project Structure

This is a uv workspace. The root `pyproject.toml` declares workspace members. Each package has its own `pyproject.toml` and uses the `src/` layout.

```
pyproject.toml                         # Workspace root — defines members

inventor_api/                          # Reusable Inventor COM wrapper
  pyproject.toml
  src/inventor_api/
    __init__.py                        # Public exports
    application.py                     # InventorApp — connect, lifecycle
    document.py                        # Document wrappers (Part, Assembly, Drawing)
    properties.py                      # iProperty access
    traversal.py                       # Assembly tree walking
    exporters.py                       # STEP/DWG/PDF export
    types.py                           # Enums, constants
    exceptions.py                      # Custom exceptions
    _com_threading.py                  # COM thread init helper
  tests/
    conftest.py
    test_types.py
    test_document.py
    test_traversal.py
    test_exporters.py

inventor_export_tool/                  # Inventor Export tool
  pyproject.toml
  src/inventor_export_tool/
    __init__.py
    __main__.py                        # Calls cli.main()
    cli.py                             # argparse CLI entry point
    gui.py                             # ExportToolGUI (ttk.Frame tab)
    models.py                          # ExportItem, ScanSummary, ExportResult
    naming.py                          # Filename composition, IDW finding
    config.py                          # JSON config persistence
    export_log.py                      # Export logging
    orchestrator.py                    # Scan + export logic
  tests/
    conftest.py
    test_naming.py
    test_models.py
    test_config.py
    test_export_log.py

inventor_simplify_tool/                # Inventor Simplify tool
  pyproject.toml
  src/inventor_simplify_tool/
    __init__.py
    __main__.py                        # Calls cli.main()
    cli.py                             # argparse CLI entry point
    gui.py                             # SimplifyToolGUI (ttk.Frame tab)
    ...
  tests/
    ...

inventor_drawing_tool/                 # Inventor Drawing Release tool
  pyproject.toml
  src/inventor_drawing_tool/
    __init__.py
    __main__.py                        # Calls cli.main()
    cli.py                             # argparse CLI entry point
    gui.py                             # DrawingToolGUI (ttk.Frame tab)
    settings_dialog.py                 # Advanced settings modal
    models.py                          # DrawingItem, RevisionData, ScanResult
    config.py                          # JSON config persistence
    scanner.py                         # Assembly scanning for drawings
    orchestrator.py                    # Scan + create + revision logic
    release_log.py                     # Release logging
  tests/
    conftest.py
    test_models.py
    test_config.py
    test_scanner.py

inventor_utils/                        # Shared utilities
  pyproject.toml
  src/inventor_utils/
    __init__.py
    filenames.py                       # sanitize_filename, find_idw_path, etc.
    config.py                          # Generic config load/save helpers
    base_logger.py                     # ToolLogger abstract base
    base_orchestrator.py               # BaseOrchestrator with callbacks
  tests/
    test_filenames.py
    test_config.py

zabra_cadabra/                         # Shell application (entry point)
  pyproject.toml
  build.py                             # PyInstaller build script
  ZabraCadabra.spec                    # PyInstaller spec
  config.json                          # Default/bundled config
  assets/                              # Logo, usage guide, etc.
  src/zabra_cadabra/
    __init__.py
    __main__.py                        # python -m zabra_cadabra
    app.py                             # main() — loads configs, runs shell
    shell.py                           # ZabraApp — Tk root, header, Notebook
    theme.py                           # Black/white ttk.Style theme
    tab_registry.py                    # TabSpec + TABS list
    telemetry/                         # Telemetry subsystem
      ...
  tests/
    conftest.py
    telemetry/
      ...
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
- Tests live inside each package: `inventor_api/tests/`, `inventor_export_tool/tests/`, etc. There is no root-level `tests/` directory.
- Tests mirror module paths within the package: e.g. `inventor_export_tool/tests/test_naming.py` mirrors `src/inventor_export_tool/naming.py`
- Use `tmp_path` for file I/O tests
- Use `unittest.mock.MagicMock` for COM objects — configure with expected attributes
- Mock factories live in the package's own `tests/conftest.py`
- Run tests for a single package: `uv run --package <package-name> pytest`

### Code Style
- Type hints on all public function signatures
- Use `dataclass` for structured data, not dicts
- Use `Enum`/`IntEnum` for constants, not magic numbers
- No docstrings on private/internal functions unless non-obvious

### Architecture Boundary
- **`zabra_cadabra`**: Shell only — owns Tk root, header, notebook, theme. No business logic.
- **`inventor_api`**: Pythonic COM wrapper. Returns its own types. No imports from tool packages.
- **`inventor_export_tool`**: App logic. Imports from `inventor_api`. Contains GUI, config, naming, orchestration, CLI.
- **`inventor_simplify_tool`**: App logic. Imports from `inventor_api`. Contains GUI, config, orchestration, CLI.
- **`inventor_drawing_tool`**: App logic. Imports from `inventor_api` and `inventor_utils`. Contains GUI, config, scanner, orchestration, CLI.
- **`inventor_utils`**: Shared pure-Python utilities. No GUI, no COM, no inventor_api imports.
- **GUI** (`gui.py` in each tool): `ttk.Frame` tab — no direct COM or inventor_api calls — goes through `orchestrator.py` on background thread.
- **CLI** (`cli.py` in each tool): argparse entry point for standalone use. `__main__.py` calls `cli.main()`.

### Adding a New Tab
1. Create a new package directory (e.g. `my_tool/`) with `pyproject.toml` and `src/my_tool/` using the src layout.
2. Add the package as a workspace member in the root `pyproject.toml`.
3. Create `gui.py` with a `ttk.Frame` subclass (accepting `parent` and optional `config` args).
4. Create `cli.py` with argparse and a `main()` function. Create `__main__.py` that calls `cli.main()`.
5. Add the package as a dependency of `zabra_cadabra` in `zabra_cadabra/pyproject.toml`.
6. Add a `TabSpec` entry in `zabra_cadabra/src/zabra_cadabra/tab_registry.py`.
7. If the tab needs config, add a loader in `zabra_cadabra/src/zabra_cadabra/app.py` and pass via `configs` dict.

### API Documentation
- All `inventor_api` public API documented in README.md
- When adding/changing public functions, update README

## MCP Servers

- **memory** — Search before exploring source files. Store non-obvious insights after tasks.
- **ide** — `getDiagnostics` for type errors. `executeCode` for Jupyter experiments.

## Common Commands

```bash
uv sync --all-packages                          # Install all workspace packages
uv run zabra-cadabra                            # Run the full GUI app
uv run inventor-export --help                   # Run export tool CLI standalone
uv run inventor-simplify --help                 # Run simplify tool CLI standalone
uv run inventor-drawing --help                 # Run drawing tool CLI standalone
uv run --package inventor-api pytest            # Test inventor_api
uv run --package inventor-export-tool pytest    # Test inventor_export_tool
uv run --package inventor-simplify-tool pytest  # Test inventor_simplify_tool
uv run --package inventor-drawing-tool pytest  # Test inventor_drawing_tool
uv run --package inventor-utils pytest         # Test inventor_utils
uv run --package zabra-cadabra pytest           # Test zabra_cadabra
uv run ruff check .                             # Lint all packages
uv run ruff format .                            # Format all packages
uv run ty check                                 # Type check
cd zabra_cadabra && uv run python build.py      # Build ZabraCadabra.exe
```
