# Export Single Parts + Folder-Default Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the export tool export a single active Part (not just assemblies), and add a toggle that defaults the output-folder picker to either the app's last-export folder or the Windows OS-wide last-used folder.

**Architecture:** Feature 2 adds `get_active_part_or_assembly()` to `inventor_api` and a part branch in the orchestrator's scan; the existing scan→plan→export pipeline already handles a single component. Feature 1 adds a `FolderDefaultMode` enum + config field, a best-effort Windows-MRU registry reader in `inventor_utils`, and a toggle button in the export GUI that selects the picker's `initialdir`.

**Tech Stack:** Python 3.13, uv workspace, pywin32 (COM, already present), Tkinter, pytest, stdlib `winreg` + `ctypes` for the Windows MRU read.

---

## File Structure

- `inventor_api/src/inventor_api/exceptions.py` — add `InventorNotPartOrAssemblyError`.
- `inventor_api/src/inventor_api/application.py` — add `get_active_part_or_assembly()`.
- `inventor_api/tests/test_application.py` — **new**, tests for the new method.
- `inventor_utils/src/inventor_utils/recent_folders.py` — **new**, Windows MRU reader.
- `inventor_utils/tests/test_recent_folders.py` — **new**, tests for the reader.
- `inventor_export_tool/src/inventor_export_tool/config.py` — add `FolderDefaultMode`, `folder_default_mode` field, load handling, `pick_initialdir()`.
- `inventor_export_tool/tests/test_config.py` — add config round-trip + `pick_initialdir` tests.
- `inventor_export_tool/src/inventor_export_tool/orchestrator.py` — part branch in `_scan_impl`, `single_part` flag in `_build_export_items`.
- `inventor_export_tool/tests/test_orchestrator.py` — add single-part-mode test.
- `inventor_export_tool/src/inventor_export_tool/gui.py` — toggle button + initialdir resolution.

---

## Task 1: `InventorNotPartOrAssemblyError` + `get_active_part_or_assembly()`

**Files:**
- Modify: `inventor_api/src/inventor_api/exceptions.py` (after the `InventorNotAssemblyError` class, ~line 38)
- Modify: `inventor_api/src/inventor_api/application.py` (imports ~line 8-12; new method after `get_active_assembly`, ~line 118)
- Test: `inventor_api/tests/test_application.py` (new)

- [ ] **Step 1: Write the failing test**

Create `inventor_api/tests/test_application.py`:

```python
"""Tests for InventorApp active-document accessors."""

from __future__ import annotations

import pytest

from inventor_api.application import InventorApp
from inventor_api.document import AssemblyDocument, InventorDocument
from inventor_api.exceptions import InventorNotPartOrAssemblyError
from inventor_api.types import DocumentType
from tests.conftest import (
    make_mock_assembly_com,
    make_mock_com_app,
    make_mock_com_document,
)


def test_get_active_part_or_assembly_returns_assembly():
    com_app = make_mock_com_app(active_doc=make_mock_assembly_com())
    app = InventorApp(com_app)

    doc = app.get_active_part_or_assembly()

    assert isinstance(doc, AssemblyDocument)


def test_get_active_part_or_assembly_returns_part():
    part_com = make_mock_com_document(document_type=DocumentType.PART)
    com_app = make_mock_com_app(active_doc=part_com)
    app = InventorApp(com_app)

    doc = app.get_active_part_or_assembly()

    assert isinstance(doc, InventorDocument)
    assert doc.document_type == DocumentType.PART


def test_get_active_part_or_assembly_rejects_drawing():
    drawing_com = make_mock_com_document(document_type=DocumentType.DRAWING)
    com_app = make_mock_com_app(active_doc=drawing_com)
    app = InventorApp(com_app)

    with pytest.raises(InventorNotPartOrAssemblyError):
        app.get_active_part_or_assembly()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package inventor-api pytest inventor_api/tests/test_application.py -v`
Expected: FAIL — `ImportError: cannot import name 'InventorNotPartOrAssemblyError'`.

- [ ] **Step 3: Add the exception**

In `inventor_api/src/inventor_api/exceptions.py`, immediately after the `InventorNotAssemblyError` class (after its docstring line), add:

```python
class InventorNotPartOrAssemblyError(InventorError):
    """Active document is neither a part nor an assembly."""
```

- [ ] **Step 4: Add the method**

In `inventor_api/src/inventor_api/application.py`, extend the exceptions import (lines 8-12) to include the new name:

```python
from inventor_api.exceptions import (
    DocumentOpenError,
    InventorNotAssemblyError,
    InventorNotPartOrAssemblyError,
    InventorNotRunningError,
)
```

Then add this method directly after `get_active_assembly` (after its `return doc`, ~line 118):

```python
    def get_active_part_or_assembly(self) -> AssemblyDocument | InventorDocument:
        """Get the active document, accepting an assembly or a part.

        Returns:
            The AssemblyDocument for an assembly, or the base InventorDocument
            for a part.

        Raises:
            InventorNotPartOrAssemblyError: If the active document is neither a
                part nor an assembly (e.g. a drawing).
        """
        doc = self.active_document
        if isinstance(doc, AssemblyDocument):
            return doc
        if doc.document_type == DocumentType.PART:
            return doc
        raise InventorNotPartOrAssemblyError(
            f"Active document '{doc.display_name}' is neither a part nor an "
            f"assembly (type: {doc.document_type.name})."
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --package inventor-api pytest inventor_api/tests/test_application.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add inventor_api/src/inventor_api/exceptions.py inventor_api/src/inventor_api/application.py inventor_api/tests/test_application.py
git commit -m "feat(inventor_api): add get_active_part_or_assembly"
```

---

## Task 2: Windows MRU reader in `inventor_utils`

**Files:**
- Create: `inventor_utils/src/inventor_utils/recent_folders.py`
- Test: `inventor_utils/tests/test_recent_folders.py` (new)

- [ ] **Step 1: Write the failing test**

Create `inventor_utils/tests/test_recent_folders.py`:

```python
"""Tests for the Windows last-used-folder reader."""

from __future__ import annotations

import inventor_utils.recent_folders as rf


def test_strip_exe_name_returns_pidl_after_utf16_terminator():
    # UTF-16LE "ab" + null terminator + PIDL bytes
    entry = b"a\x00b\x00\x00\x00PIDL"
    assert rf._strip_exe_name(entry) == b"PIDL"


def test_get_last_used_folder_returns_none_when_key_missing(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no such key")

    monkeypatch.setattr(rf.winreg, "OpenKey", boom)

    assert rf.get_last_used_folder() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package inventor-utils pytest inventor_utils/tests/test_recent_folders.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'inventor_utils.recent_folders'`.

- [ ] **Step 3: Write the implementation**

Create `inventor_utils/src/inventor_utils/recent_folders.py`:

```python
"""Best-effort reader for the Windows shell 'last visited folder' MRU.

Windows records, per executable, the folder last opened in a common file
dialog under the ComDlg32\\LastVisitedPidlMRU registry key. The MRUListEx
value orders entries by recency across all applications, so the top entry's
trailing PIDL is the folder most recently used by any program.
"""

from __future__ import annotations

import ctypes
import os
import winreg

_MRU_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer"
    r"\ComDlg32\LastVisitedPidlMRU"
)


def get_last_used_folder() -> str | None:
    """Return the folder most recently used by any app's file dialog, or None.

    Returns None on any failure, or if the resolved path is not an existing
    directory. The registry layout is undocumented, so every failure mode
    falls back to None.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _MRU_KEY) as key:
            order, _ = winreg.QueryValueEx(key, "MRUListEx")
            first = int.from_bytes(order[0:4], "little")
            if first == 0xFFFFFFFF:
                return None
            entry, _ = winreg.QueryValueEx(key, str(first))
        path = _pidl_to_path(_strip_exe_name(entry))
        if path and os.path.isdir(path):
            return path
        return None
    except Exception:
        return None


def _strip_exe_name(entry: bytes) -> bytes:
    """Skip the leading null-terminated UTF-16 exe name, return the PIDL bytes."""
    i = 0
    while i + 1 < len(entry):
        if entry[i] == 0 and entry[i + 1] == 0:
            return entry[i + 2 :]
        i += 2
    return entry


def _pidl_to_path(pidl: bytes) -> str | None:
    buf = ctypes.create_unicode_buffer(260)
    pidl_buf = ctypes.create_string_buffer(pidl, len(pidl))
    ok = ctypes.windll.shell32.SHGetPathFromIDListW(pidl_buf, buf)
    return buf.value or None if ok else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package inventor-utils pytest inventor_utils/tests/test_recent_folders.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add inventor_utils/src/inventor_utils/recent_folders.py inventor_utils/tests/test_recent_folders.py
git commit -m "feat(inventor_utils): add Windows last-used-folder reader"
```

---

## Task 3: `FolderDefaultMode` config + `pick_initialdir`

**Files:**
- Modify: `inventor_export_tool/src/inventor_export_tool/config.py`
- Test: `inventor_export_tool/tests/test_config.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `inventor_export_tool/tests/test_config.py`:

```python
def test_config_round_trips_folder_default_mode(tmp_path):
    from inventor_export_tool.config import (
        AppConfig,
        FolderDefaultMode,
        load_config,
        save_config,
    )

    path = tmp_path / "config.json"
    cfg = AppConfig(folder_default_mode=FolderDefaultMode.WINDOWS_RECENT)
    save_config(cfg, path)

    loaded = load_config(path)

    assert loaded.folder_default_mode == FolderDefaultMode.WINDOWS_RECENT


def test_load_config_defaults_mode_when_missing(tmp_path):
    from inventor_export_tool.config import FolderDefaultMode, load_config

    path = tmp_path / "config.json"
    path.write_text('{"output_folder": "C:/x"}', encoding="utf-8")

    loaded = load_config(path)

    assert loaded.folder_default_mode == FolderDefaultMode.LAST_EXPORT


def test_load_config_tolerates_unknown_mode(tmp_path):
    from inventor_export_tool.config import FolderDefaultMode, load_config

    path = tmp_path / "config.json"
    path.write_text('{"folder_default_mode": "bogus"}', encoding="utf-8")

    loaded = load_config(path)

    assert loaded.folder_default_mode == FolderDefaultMode.LAST_EXPORT


def test_pick_initialdir_field_value_wins(tmp_path):
    from inventor_export_tool.config import FolderDefaultMode, pick_initialdir

    got = pick_initialdir(
        " C:/typed ", FolderDefaultMode.WINDOWS_RECENT, "C:/last", "C:/recent"
    )
    assert got == "C:/typed"


def test_pick_initialdir_windows_recent_mode():
    from inventor_export_tool.config import FolderDefaultMode, pick_initialdir

    got = pick_initialdir("", FolderDefaultMode.WINDOWS_RECENT, "C:/last", "C:/recent")
    assert got == "C:/recent"


def test_pick_initialdir_windows_recent_falls_back_to_last_export():
    from inventor_export_tool.config import FolderDefaultMode, pick_initialdir

    got = pick_initialdir("", FolderDefaultMode.WINDOWS_RECENT, "C:/last", None)
    assert got == "C:/last"


def test_pick_initialdir_last_export_mode():
    from inventor_export_tool.config import FolderDefaultMode, pick_initialdir

    got = pick_initialdir("", FolderDefaultMode.LAST_EXPORT, "C:/last", "C:/recent")
    assert got == "C:/last"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'FolderDefaultMode'`.

- [ ] **Step 3: Add the enum, field, and helper**

In `inventor_export_tool/src/inventor_export_tool/config.py`:

Extend the imports at the top (after the existing stdlib imports):

```python
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
```

Add the enum after the two `_DEFAULT_PRESET_*` constants (~line 14):

```python
class FolderDefaultMode(str, Enum):
    """Where the output-folder picker's initial directory comes from."""

    LAST_EXPORT = "last_export"
    WINDOWS_RECENT = "windows_recent"
```

Add the field to `AppConfig`, immediately after `prompt_folder_on_export` (line 42):

```python
    folder_default_mode: FolderDefaultMode = FolderDefaultMode.LAST_EXPORT
```

In `load_config`, add `"folder_default_mode"` to the `scalar_fields` set, then convert it to the enum just before the `try: config = AppConfig(**kwargs)` block (after the `naming_presets` handling, ~line 99):

```python
    raw_mode = kwargs.get("folder_default_mode")
    if raw_mode is not None:
        try:
            kwargs["folder_default_mode"] = FolderDefaultMode(raw_mode)
        except ValueError:
            kwargs.pop("folder_default_mode")
```

Add the pure helper at the end of the file (after `save_config`):

```python
def pick_initialdir(
    field_value: str,
    mode: FolderDefaultMode,
    last_export_folder: str,
    windows_recent: str | None,
) -> str:
    """Choose the folder picker's initial directory.

    A non-empty current field value always wins. Otherwise the mode decides:
    WINDOWS_RECENT prefers the OS last-used folder (falling back to the last
    export folder), LAST_EXPORT uses the last export folder. Empty everywhere
    falls back to the user's home directory.
    """
    field_value = field_value.strip()
    if field_value:
        return field_value
    if mode == FolderDefaultMode.WINDOWS_RECENT:
        if windows_recent:
            return windows_recent
        if last_export_folder:
            return last_export_folder
        return os.path.expanduser("~")
    if last_export_folder:
        return last_export_folder
    return os.path.expanduser("~")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_config.py -v`
Expected: PASS (all config tests, including the 7 new ones).

- [ ] **Step 5: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/config.py inventor_export_tool/tests/test_config.py
git commit -m "feat(export): add FolderDefaultMode config + pick_initialdir"
```

---

## Task 4: Single-part branch in the orchestrator

**Files:**
- Modify: `inventor_export_tool/src/inventor_export_tool/orchestrator.py`
- Test: `inventor_export_tool/tests/test_orchestrator.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `inventor_export_tool/tests/test_orchestrator.py`:

```python
def test_build_export_items_single_part_ignores_inclusion_filters():
    from inventor_export_tool.config import AppConfig
    from inventor_export_tool.models import ComponentInfo
    from inventor_export_tool.orchestrator import _build_export_items

    comp = ComponentInfo(
        source_path=r"C:\Projects\P-100089.ipt",
        display_name="P-100089",
        document_type="part",
        revision="A",
        is_top_level=True,
        idw_path=None,
    )
    # Filters that would normally drop a top-level part:
    config = AppConfig(
        include_parts=False,
        include_top_level=False,
        export_step=True,
        export_dwg=False,
        export_pdf=False,
    )

    items = _build_export_items(
        [comp], config, r"C:\out", {}, single_part=True
    )

    assert len(items) == 1
    assert items[0].export_type == "step"
    assert items[0].output_filename.endswith(".step")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_orchestrator.py::test_build_export_items_single_part_ignores_inclusion_filters -v`
Expected: FAIL — `TypeError: _build_export_items() got an unexpected keyword argument 'single_part'`.

- [ ] **Step 3: Add the `single_part` parameter and guard**

In `inventor_export_tool/src/inventor_export_tool/orchestrator.py`, change the `_build_export_items` signature to add the flag:

```python
def _build_export_items(
    components: list[ComponentInfo],
    config: AppConfig,
    output_folder: str,
    doc_cache: dict[str, "InventorDocument"],
    single_part: bool = False,
) -> list[ExportItem]:
```

Wrap the four `continue` filter checks at the top of the `for comp in components:` loop so they are skipped in single-part mode:

```python
    for comp in components:
        if not single_part:
            if comp.is_top_level and not config.include_top_level:
                continue
            if (
                comp.document_type == "assembly"
                and not comp.is_top_level
                and not config.include_subassemblies
            ):
                continue
            if comp.document_type == "part" and not config.include_parts:
                continue
            if _matches_excluded_prefix(comp.display_name, excluded_prefixes):
                continue
```

(The rest of the loop body — base-name rendering and the `export_step` / `idw_path` blocks — is unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_orchestrator.py::test_build_export_items_single_part_ignores_inclusion_filters -v`
Expected: PASS.

- [ ] **Step 5: Wire the part branch into `_scan_impl`**

In the same file, extend the traversal import (line ~14) — it already imports `DiscoveredComponent, walk_assembly`, so no change there. Add an `AssemblyDocument` import after the existing `from inventor_api import ...` line:

```python
from inventor_api.document import AssemblyDocument
```

Replace the assembly-acquisition block in `_scan_impl` (currently lines ~181-190) with:

```python
        self._emit("Getting active assembly or part...")
        doc = self._app.get_active_part_or_assembly()
        self._assembly_name = doc.display_name
        self._assembly_path = doc.full_path
        self._emit(f"Document: {self._assembly_name}")

        self._emit("Scanning document...")
        if isinstance(doc, AssemblyDocument):
            discovered = walk_assembly(
                doc,
                include_suppressed=self._config.include_suppressed,
            )
            single_part = False
        else:
            discovered = [
                DiscoveredComponent(document=doc, is_top_level=True, depth=0)
            ]
            single_part = True
```

Then update the `_build_export_items` call (currently ~line 221) to pass the flag:

```python
        items = _build_export_items(
            components, self._config, effective_folder, self._doc_cache, single_part=single_part
        )
```

- [ ] **Step 6: Run the full orchestrator test module**

Run: `uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_orchestrator.py -v`
Expected: PASS (existing tests still green, new test green).

- [ ] **Step 7: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/orchestrator.py inventor_export_tool/tests/test_orchestrator.py
git commit -m "feat(export): support exporting a single active part"
```

---

## Task 5: GUI toggle button + initialdir wiring

**Files:**
- Modify: `inventor_export_tool/src/inventor_export_tool/gui.py`

This task is GUI wiring (the pure logic it depends on — `pick_initialdir`, `get_last_used_folder`, `FolderDefaultMode` — is already tested in Tasks 2-3), so it has no new unit test. Verify by import + a smoke construction at the end.

- [ ] **Step 1: Add imports**

In `inventor_export_tool/src/inventor_export_tool/gui.py`, add runtime imports near the top (after the existing `from typing import TYPE_CHECKING` block, around line 12). Do **not** put these under `TYPE_CHECKING`:

```python
from inventor_export_tool.config import FolderDefaultMode, pick_initialdir
from inventor_utils.recent_folders import get_last_used_folder
```

- [ ] **Step 2: Initialise the mode attribute in `__init__`**

In `__init__`, before the `self._build_ui()` call (after `self._last_log_path = None`, ~line 29), add:

```python
        self._folder_mode: FolderDefaultMode = FolderDefaultMode.LAST_EXPORT
```

- [ ] **Step 3: Add the toggle button to the output row**

In `_build_ui`, the output section currently puts "Browse..." at `row=0, column=1` (line 69). Add the toggle button at `row=0, column=2` right after it:

```python
        ttk.Button(out_frame, text="Browse...", command=self._browse_output).grid(row=0, column=1)
        self._folder_mode_btn = ttk.Button(
            out_frame, text="Default folder: Last export", command=self._toggle_folder_mode
        )
        self._folder_mode_btn.grid(row=0, column=2, padx=(4, 0))
        out_frame.columnconfigure(0, weight=1)
```

(Replace the existing two lines — the Browse button line and the `out_frame.columnconfigure(0, weight=1)` line — with the block above so the new button sits between them.)

- [ ] **Step 4: Add the toggle + label-update + initialdir helpers**

Add these three methods to the class (place them next to `_browse_output`, ~line 215):

```python
    def _toggle_folder_mode(self) -> None:
        self._folder_mode = (
            FolderDefaultMode.WINDOWS_RECENT
            if self._folder_mode == FolderDefaultMode.LAST_EXPORT
            else FolderDefaultMode.LAST_EXPORT
        )
        self._update_folder_mode_button()
        self._save_config()

    def _update_folder_mode_button(self) -> None:
        label = (
            "Default folder: Windows recent"
            if self._folder_mode == FolderDefaultMode.WINDOWS_RECENT
            else "Default folder: Last export"
        )
        self._folder_mode_btn.configure(text=label)

    def _picker_initialdir(self) -> str:
        recent = (
            get_last_used_folder()
            if self._folder_mode == FolderDefaultMode.WINDOWS_RECENT
            else None
        )
        return pick_initialdir(
            self._output_var.get(), self._folder_mode, self._config.output_folder, recent
        )
```

- [ ] **Step 5: Use the initialdir helper in both pickers**

Replace `_browse_output` (lines 212-215) with:

```python
    def _browse_output(self) -> None:
        path = filedialog.askdirectory(
            title="Select Output Folder", initialdir=self._picker_initialdir()
        )
        if path:
            self._output_var.set(path)
```

In `_resolve_output_folder`, replace the `initialdir=...` argument (line 365) so it uses the helper:

```python
        if prompt:
            path = filedialog.askdirectory(
                title="Select Output Folder",
                initialdir=self._picker_initialdir(),
            )
            return path if path else None
        return current
```

- [ ] **Step 6: Persist and load the mode**

In `_load_config`, after `self._prompt_folder_var.set(c.prompt_folder_on_export)` (line ~229), add:

```python
        self._folder_mode = c.folder_default_mode
        self._update_folder_mode_button()
```

In `_save_config`, after `self._config.prompt_folder_on_export = self._prompt_folder_var.get()`, add:

```python
        self._config.folder_default_mode = self._folder_mode
```

In `_get_current_config`, add the field to the `AppConfig(...)` constructor (after `prompt_folder_on_export=...`, line 269):

```python
            folder_default_mode=self._folder_mode,
```

- [ ] **Step 7: Smoke-check the module imports and the tab constructs**

Run:
```bash
uv run --package inventor-export-tool python -c "import tkinter as tk; from inventor_export_tool.config import AppConfig; from inventor_export_tool.gui import ExportFrame if False else None; print('import ok')"
```
Then run the full GUI-adjacent test suite to confirm nothing regressed:
Run: `uv run --package inventor-export-tool pytest -v`
Expected: PASS (all tests).

> Note: the class name in the import smoke-check is whatever the `ttk.Frame` subclass is actually called in `gui.py`; if `ExportFrame` is wrong, just run the pytest line — that is the real gate.

- [ ] **Step 8: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/gui.py
git commit -m "feat(export): folder-default mode toggle in export GUI"
```

---

## Task 6: Verify, build, distribute

**Files:** none (verification + build + housekeeping)

- [ ] **Step 1: Lint, format, type-check**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
```
Expected: no errors. If `ruff format --check` reports files, run `uv run ruff format .` and re-commit.

- [ ] **Step 2: Full test sweep across touched packages**

Run:
```bash
uv run --package inventor-api pytest
uv run --package inventor-utils pytest
uv run --package inventor-export-tool pytest
```
Expected: all pass.

- [ ] **Step 3: Build the single-file exe**

Run:
```bash
cd zabra_cadabra && uv run python build.py
```
Expected: build completes; exe produced (confirm the output path printed by `build.py`).

- [ ] **Step 4: Move the two feedback files to solved/**

```bash
git mv docs/User_feedback/feedback_20260603_084547_OleMStasionary.md docs/User_feedback/solved/
git mv docs/User_feedback/feedback_20260604_124746_OleMStasionary.md docs/User_feedback/solved/
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: resolve folder-default + single-part feedback; rebuild exe"
```

---

## Self-Review Notes

- **Spec coverage:** Feature 2 entry point (Task 1) + scan branch & filter bypass (Task 4); Feature 1 enum/field/helper (Task 3), MRU reader (Task 2), toggle button + initialdir + persistence (Task 5); distribution (Task 6). All spec sections mapped.
- **Type consistency:** `FolderDefaultMode` / `pick_initialdir` / `get_last_used_folder` / `get_active_part_or_assembly` / `_build_export_items(single_part=...)` used with identical signatures across tasks.
- **Open risk:** the exact `ttk.Frame` subclass name in `gui.py` (Step 5 of Task 5) — the pytest run is the real gate, not the import smoke-check. The `build.py` output path is printed by that script, not assumed here.
