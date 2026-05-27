# Testing Conventions

- **Unit tests required** for all pure functions and all `inventor_api` public API
- Tests live inside each package: `inventor_api/tests/`, `inventor_export_tool/tests/`, etc. No root-level `tests/` directory.
- Tests mirror module paths: e.g. `inventor_export_tool/tests/test_naming.py` mirrors `src/inventor_export_tool/naming.py`
- Use `tmp_path` for file I/O tests
- Use `unittest.mock.MagicMock` for COM objects — configure with expected attributes
- Mock factories live in the package's own `tests/conftest.py`
- Run per-package: `uv run --package <package-name> pytest`
