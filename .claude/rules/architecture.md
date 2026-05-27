# Architecture Boundaries

- **`zabra_cadabra`**: Shell only — owns Tk root, header, notebook, theme. No business logic.
- **`inventor_api`**: Pythonic COM wrapper. Returns its own types. No imports from tool packages.
- **`inventor_export_tool`**: App logic. Imports from `inventor_api`. Contains GUI, config, naming, orchestration, CLI.
- **`inventor_simplify_tool`**: App logic. Imports from `inventor_api`. Contains GUI, config, orchestration, CLI.
- **`inventor_drawing_tool`**: App logic. Imports from `inventor_api` and `inventor_utils`. Contains GUI, config, scanner, orchestration, CLI.
- **`inventor_utils`**: Shared pure-Python utilities. No GUI, no COM, no inventor_api imports.
- **GUI** (`gui.py` in each tool): `ttk.Frame` tab — no direct COM or inventor_api calls — goes through `orchestrator.py` on background thread.
- **CLI** (`cli.py` in each tool): argparse entry point for standalone use. `__main__.py` calls `cli.main()`.

## inventor_api Rules

- **Library-grade code** — no app-specific logic, no GUI references
- **Dependency injection** — all classes accept COM object in constructor, enabling mock testing
- **Custom exceptions** — never let raw `pywintypes.com_error` escape; wrap in `InventorError` subclasses
- **Every public class/function must have tests** using mock COM objects
- Docstrings on all public API (this is a library)
- All public API documented in README.md — update when adding/changing public functions
