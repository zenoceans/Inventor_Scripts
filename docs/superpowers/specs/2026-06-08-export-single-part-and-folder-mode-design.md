# Design: Export single parts + folder-default mode toggle

**Date:** 2026-06-08
**Tool:** `inventor_export_tool` (+ `inventor_api`, `inventor_utils`)
**Source:** Two unsolved user feedback reports in `docs/User_feedback/`:

- `feedback_20260603_084547` — "When prompting selecting folder, the folder shown
  should be the last folder used, regardless if the folder was used by another
  program or done manually."
- `feedback_20260604_124746` — "being able to export single parts as well"
  (currently raises `InventorNotAssemblyError` when a Part is the active document).

---

## Feature 2 — Export single parts

### Problem

`orchestrator._scan_impl` starts with `self._app.get_active_assembly()`, which raises
`InventorNotAssemblyError` when the active document is a Part. The rest of the
scan→plan→export pipeline (`_to_component_info`, `_build_export_items`,
`_export_item`, `export_step`, `export_drawing`) already handles single parts —
only the entry point is assembly-locked.

### Approach: auto-detect at the entry point

No new button or mode. The tool accepts whatever document is active.

1. **`inventor_api/application.py`**
   - Add `get_active_part_or_assembly() -> AssemblyDocument | InventorDocument`.
     Returns the assembly for `.iam`, or the base part document for `.ipt`.
   - Add exception `InventorNotPartOrAssemblyError(InventorError)` in
     `inventor_api/exceptions.py`, raised only when the active document is a
     drawing (or some other non-part/non-assembly type) or nothing is open.
   - Keep `get_active_assembly()` unchanged (still used elsewhere / tested).

2. **`inventor_export_tool/orchestrator.py` (`_scan_impl`)**
   - Replace `assembly = self._app.get_active_assembly()` with
     `doc = self._app.get_active_part_or_assembly()`.
   - Branch:
     - Assembly → `discovered = walk_assembly(doc, include_suppressed=...)`
       (unchanged).
     - Part → `discovered = [DiscoveredComponent(document=doc, is_top_level=True, depth=0)]`.
   - Keep `self._assembly_name` / `self._assembly_path` populated from `doc`
     (used by log filename + summary); they apply to a part equally.

3. **Single-part filter handling**
   - In single-part mode the active part is the thing the user explicitly opened
     to export, so it must always export. Bypass the assembly-oriented inclusion
     toggles (`include_top_level`, `include_parts`) for that one component.
     Only the format toggles (`export_step` / `export_dwg` / `export_pdf`) and the
     `.idw` lookup apply.
   - Implementation: pass a flag into `_build_export_items` (e.g.
     `single_part: bool`) that skips the `include_top_level` / `include_parts`
     `continue` checks. Prefix-exclusion is also skipped in single-part mode (the
     user chose this specific part).

4. **Text**
   - "Getting active assembly..." → "Getting active assembly or part...".
   - `f"Assembly: {name}"` → `f"Document: {name}"`.

### Reuse (unchanged)

`_to_component_info` already maps part vs assembly. `_build_export_items` already
emits STEP for any component and DWG/PDF when `idw_path` is set. `find_idw_path`
already resolves a part's sibling `.idw`. `export_step` accepts any document;
`export_drawing` opens the IDW. No exporter changes.

---

## Feature 1 — Folder-default mode toggle

### Problem

The picker's `initialdir` is the app's own remembered `output_folder` (or `~`).
The user wants the option to instead default to the folder last used by the
Windows OS across all programs.

### Approach: two-mode toggle button, mode persisted in config

1. **Config — `inventor_export_tool/config.py`**
   - New `Enum` `FolderDefaultMode` with members `LAST_EXPORT` and `WINDOWS_RECENT`.
   - New `AppConfig` field `folder_default_mode: FolderDefaultMode = FolderDefaultMode.LAST_EXPORT`.
   - Serialize as its string value in JSON; `load_config` migration tolerates a
     missing/unknown value by falling back to `LAST_EXPORT`.

2. **Windows MRU reader — `inventor_utils/recent_folders.py` (new)**
   - `get_last_used_folder() -> str | None`.
   - Reads `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\ComDlg32\LastVisitedPidlMRU`
     via `winreg`: read `MRUListEx` to find the most-recent entry index, read that
     entry's binary value, skip the leading null-terminated UTF-16 executable
     name, decode the trailing PIDL to a filesystem path with
     `ctypes.windll.shell32.SHGetPathFromIDListW`.
   - Returns the path if it exists and is a directory, else `None`. Entire body
     wrapped in `try/except` — registry layout is undocumented/best-effort, so any
     failure returns `None`.
   - Pure utility: stdlib `winreg` + `ctypes` only. No GUI, no COM, no
     `inventor_api` import — fits `inventor_utils` boundary.

3. **GUI — `inventor_export_tool/gui.py`**
   - Add a single toggle button near "Browse". Label shows the active mode:
     `Default folder: Last export` ⟷ `Default folder: Windows recent`.
   - Click flips `folder_default_mode`, updates the label, and saves config.
   - Picker `initialdir` resolution (used by both `_browse_output` and
     `_resolve_output_folder`):
     - The current output-field value still wins if non-empty (an explicitly set
       output folder).
     - Else, by mode:
       - `LAST_EXPORT` → `config.output_folder`, fallback `~`.
       - `WINDOWS_RECENT` → `get_last_used_folder()`, fallback `config.output_folder`,
         then `~`.

4. **Persist last-exported folder**
   - After an export run completes successfully, write the resolved output folder
     back to `config.output_folder` (and into the field), so `LAST_EXPORT` mode
     reflects the folder actually exported to rather than only the field value at
     shutdown.

---

## Testing

- `inventor_api`: unit test `get_active_part_or_assembly` with mock part / mock
  assembly / mock drawing (raises `InventorNotPartOrAssemblyError`).
- `inventor_export_tool`:
  - `_build_export_items` in single-part mode produces the expected items even
    when `include_parts` / `include_top_level` are `False`.
  - config round-trips `folder_default_mode`; load tolerates missing/unknown value.
- `inventor_utils`: `get_last_used_folder` returns `None` cleanly when the
  registry key is absent (monkeypatch `winreg` to raise) — the failure path is the
  one we must guarantee.
- GUI mode-toggle logic (label + initialdir selection) tested at the function
  level where practical; the MRU read is mocked.

## Verification

- `uv run ruff check .` and `uv run ruff format --check .`
- `uv run ty check`
- `uv run --package inventor-api pytest`
- `uv run --package inventor-export-tool pytest`
- `uv run --package inventor-utils pytest`

## Distribution

1. All tests / lint / type-check pass.
2. Rebuild single-file exe: `cd zabra_cadabra && uv run python build.py`.
3. Move the two feedback files into `docs/User_feedback/solved/`.

## Out of scope

- Decoding `OpenSavePidlMRU` per file extension.
- Any change to drawing export, naming presets, or telemetry.
- A separate "export part" button/mode (auto-detect covers it).
