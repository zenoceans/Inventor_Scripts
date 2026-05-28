# Export Tool — Naming Presets & Streamlined Flow

**Date:** 2026-05-28
**Source:** User feedback `docs/User_feedback/feedback_20260527_131752_OleMStasionary.md` and reference script `docs/User_feedback/main OleM.py`

## Background

OleM gave three pieces of feedback on the Inventor Export tool:

1. **Naming Scheme** — let the user choose where ID, Name, and Revision come from.
2. **Browse-folder prompt on export** — pop a folder picker when starting an export.
3. **No required Scan before Export** — the current two-button flow (Scan → Export) is friction.

The reference script `main OleM.py` shows OleM's preferred flow: connect to the active doc, pick an output folder, export — naming built from `PartNumber - Description - RevX` with revision read from the IDW. He wants the GUI to feel that direct, but with the configurability to handle other naming conventions.

## Goals

- Replace the hard-coded `display_name + revision` naming with a token-based template system, configurable per user via named presets.
- Reduce export to one click; pop the folder picker inline when needed.
- Keep the "scan-and-preview" capability for advanced users, but make it optional.

## Non-goals

- IDW revision-table lookup (the reference script does this; user opted for IPT/IAM `Revision Number` iProperty only — simpler and consistent across formats).
- Per-tool naming presets in other tools (drawing, simplify). Scope is the export tool only.
- A GUI for editing User Defined iProperties — users type those names manually into the template.

## Architecture overview

Three areas change:

1. **`inventor_api`** — small read-only iProperty helper.
2. **`inventor_export_tool`** — new template engine, new preset dialog, GUI rework, orchestrator change, config schema additions.
3. **`inventor_utils`** — remove `compose_filename` (no longer used).

## Detailed design

### 1. Data model & config

In `inventor_export_tool/config.py`:

```python
@dataclass
class NamingPreset:
    name: str
    template: str
```

Add to `AppConfig`:

| Field | Type | Default |
|---|---|---|
| `naming_presets` | `list[NamingPreset]` | `[NamingPreset("OleM Default", "{Part Number} - {Description} - Rev{Revision Number}")]` |
| `active_preset_name` | `str` | `"OleM Default"` |
| `prompt_folder_on_export` | `bool` | `False` |

**Migration:** `load_config` seeds the default preset if `naming_presets` is missing or empty after JSON load. `active_preset_name` is forced to point at an existing preset; if it doesn't match anything, it's reset to the first preset's name.

**Retired:** `compose_filename(display_name, revision, extension)` is removed from `inventor_utils/filenames.py`. It's only used in the export tool. Re-exports in `inventor_export_tool/naming.py` are removed too. `sanitize_filename`, `find_idw_path`, `is_content_center_path` stay.

### 2. iProperty helper on `inventor_api`

Add to `InventorDocument` (in `inventor_api/document.py` or equivalent):

```python
def get_iproperty(self, name: str) -> str | None:
    """Look up an iProperty by display name across all property sets.

    Returns the value as a string, or None if the property is missing
    or its value is None. Search order: Design Tracking Properties,
    Inventor Summary Information, Inventor Document Summary Information,
    Inventor User Defined Properties. Case-insensitive on the name.
    """
```

Wraps `pywintypes.com_error` in the standard `InventorError` subclass. Returns `None` (not "") so the template engine can distinguish "missing" from "explicitly empty".

Unit test: build a `MagicMock` COM doc with a couple of PropertySets, verify it finds names from each set and returns `None` for missing names.

### 3. Template engine — `inventor_export_tool/templates.py`

One public function plus a constant:

```python
def render_template(template: str, doc: InventorDocument, fallback_filename: str) -> str:
    """Render `template` against `doc`'s iProperties.

    Tokens are `{Property Name}` (case-insensitive, spaces allowed).
    Special token `{filename}` → file stem of `doc.full_path`.
    Missing/None values render as empty string.

    Post-processing: sanitize for Windows filenames, collapse runs of
    whitespace, strip trailing dashes/spaces. If the result is empty
    after all of that, return `fallback_filename`.
    """

BUILTIN_TOKENS: list[str] = [
    "filename",
    "Part Number", "Description", "Project", "Revision Number",
    "Title", "Subject", "Author", "Comments",
    "Category", "Company", "Manager",
    "Material", "Cost Center", "Checked By", "Engineer Approved By",
]
```

`BUILTIN_TOKENS` is the chip list shown in the preset dialog. It's not a whitelist — any iProperty name typed manually still resolves.

**Implementation notes:**
- Token regex: `\{([^{}]+)\}` — content between braces, no nesting.
- Special-case `{filename}` (case-insensitive) before iProperty lookup.
- Sanitize the *final* string, not individual tokens, so a token containing a slash doesn't get mangled before substitution (caller's problem if they want literal `/` in a value).
- Whitespace collapse: `re.sub(r"\s+", " ", result).strip()`.
- Strip trailing/leading dashes-and-spaces: `result.strip(" -")`.
- Empty after sanitize → `fallback_filename`.

**Unit tests** (no Inventor needed — mock `doc.get_iproperty`):
- Each builtin token renders.
- `{filename}` returns file stem.
- Missing token → empty + whitespace collapse works (`Part - {Description} - Rev` with empty Description → `Part - Rev`).
- Invalid filename chars in iProperty value are sanitized.
- All-missing tokens → fallback_filename returned.
- Custom user-defined property (mocked) renders.
- Case-insensitive: `{PART NUMBER}` and `{part number}` both work.

### 4. Orchestrator change

In `inventor_export_tool/orchestrator.py`, `_build_export_items` currently calls `compose_filename(comp.display_name, comp.revision, ext)` three times per component. Replace with one rendered base name per component:

```python
preset = config.active_preset()  # helper on AppConfig
base_name = render_template(
    preset.template, doc, fallback_filename=comp.display_name
)
# Then per-format:
filename = sanitize_filename(base_name) + f".{ext}"
```

`active_preset()` looks up `naming_presets` by `active_preset_name`. The doc reference comes from `_doc_cache` (already populated during `walk_assembly`). Duplicate resolution (`_2`, `_3`) is unchanged — it operates on the rendered names.

`ComponentInfo.revision` stays on the dataclass but is no longer special-cased by the orchestrator. It's still useful in logs and for tools that may want it.

### 5. Naming Preset dialog — `inventor_export_tool/naming_dialog.py`

`NamingPresetDialog(parent, presets, active_name) -> (presets, active_name) | None`. Modeled after `settings_dialog.py`. Modal, blocks until OK/Cancel. Returns `None` on Cancel.

**Widgets, top-to-bottom:**

| Widget | Behavior |
|---|---|
| `Listbox` (presets) | Shows names; active preset prefixed with `* `. Single-select. |
| `[+ Add]` button | Opens a small entry dialog for a new preset name; new preset is created with template `""` and selected. |
| `[Rename]` button | Renames the selected preset. Enforces uniqueness. |
| `[Delete]` button | Removes the selected preset. Disabled when only one preset remains. If the deleted preset was active, active becomes the first remaining preset. |
| `[Set Active]` button | Marks the selected preset as active. Double-click on listbox row does the same. |
| `Entry` (template) | Loads the selected preset's template; edits write through to the in-memory preset live. Refreshes preview on every keystroke. |
| Token chip `Frame` | Buttons for each name in `BUILTIN_TOKENS`. Click inserts `{Name}` at cursor position in the template entry. |
| `Label` (preview) | Live-rendered against the current Inventor active doc. If no Inventor connection or no active doc → `(no preview — open a part or assembly in Inventor)`. |
| `[OK]` / `[Cancel]` | OK validates and returns. Cancel discards. |

**State management:** the dialog works on a `copy.deepcopy` of the presets list. OK assigns the modified list back; Cancel does nothing.

**Validation on OK:**
- ≥ 1 preset exists (enforced by Delete-disable, but rechecked).
- All preset names are non-empty and unique (case-insensitive).
- `active_name` matches an existing preset (auto-corrected if not).

**Preview implementation:** the dialog tries `InventorApp.connect()` lazily. If it fails (Inventor not running) → static fallback message. If it succeeds → `get_active_document()` and `render_template` against it. Errors during preview are caught and shown as `(preview unavailable: <reason>)` rather than crashing the dialog. This runs synchronously on the UI thread — preview rendering is just iProperty reads, no exports.

### 6. Main GUI changes — `inventor_export_tool/gui.py`

**New "Naming" row** inside (or just above) the "Export Options" `LabelFrame`:

```
Naming preset: [OleM Default       ▼]  [Manage...]
```

- `Combobox` populated from `config.naming_presets` (read-only).
- Changing selection updates `config.active_preset_name` and saves config immediately.
- `[Manage...]` opens `NamingPresetDialog`; after OK, refreshes the combobox values and selection.

**Output Folder section** gains:

```
[ ] Prompt for folder on every export
```

A `Checkbutton` bound to `self._prompt_folder_var`. Persists to `config.prompt_folder_on_export`.

**Buttons row reshuffle:**

| Before | After |
|---|---|
| `[Scan Assembly]` `[Run Export]` `[Cancel]` ... `[Open Log]` `[Settings...]` | `[Run Export]` `[Cancel]` ... `[Preview]` `[Open Log]` `[Settings...]` |

- "Run Export" is the primary action, listed first.
- "Scan Assembly" is renamed to "Preview" and moved to the right.

**`_on_export` handler — new logic:**

```python
def _on_export(self) -> None:
    folder = self._resolve_output_folder()
    if folder is None:
        return  # user cancelled
    self._output_var.set(folder)
    self._save_config()
    self._set_working(True)
    self._cancel_event.clear()
    self._progress_var.set(0)
    self._progress_label.configure(text="Exporting...")
    config = self._get_current_config()
    self._worker_thread = Thread(
        target=self._export_worker, args=(config, folder), daemon=True
    )
    self._worker_thread.start()

def _resolve_output_folder(self) -> str | None:
    """Returns the folder to use, or None if user cancelled the picker.

    - prompt_folder_on_export=True → always pick, starting from current value.
    - Folder field empty → pick, starting from last-used.
    - Else → return current value without prompting.
    """
```

The current `_scan_summary` / `_on_scan` / two-step flow goes away. `_export_worker` becomes single-pass:

```python
def _export_worker(self, config: AppConfig, output_folder: str) -> None:
    from inventor_api._com_threading import com_thread_scope
    from inventor_export_tool.orchestrator import ExportOrchestrator
    try:
        with com_thread_scope():
            config = replace(config, output_folder=output_folder)
            orch = ExportOrchestrator(
                config=config,
                progress_callback=self.set_progress,
                log_callback=self.log,
            )
            summary = orch.scan()
            orch.export(summary, self._cancel_event)
            self._queue.put(("export_done", orch.last_log_path))
    except Exception as e:
        logging.getLogger(__name__).exception("Worker thread failed")
        self._queue.put(("error", str(e)))
```

**`_on_preview` handler** (renamed Scan, simplified):

```python
def _on_preview(self) -> None:
    # Validate folder same way as export, so previews show realistic paths
    folder = self._resolve_output_folder()
    if folder is None: return
    self._output_var.set(folder)
    self._save_config()
    # Run scan-only on worker; do NOT export.
    config = self._get_current_config()
    self._worker_thread = Thread(
        target=self._preview_worker, args=(config, folder), daemon=True
    )
    self._worker_thread.start()
```

`_preview_worker` calls `scan()` and posts `("preview_done", summary)`; no caching of orchestrator across handlers. The log area already shows each item via `_emit` inside scan.

### 7. CLI

`inventor_export_tool/cli.py` keeps argparse semantics. New options:
- `--preset <name>` — name of a preset from the loaded config. Defaults to `active_preset_name`. Errors clearly if not found.
- No `--template` option — keep CLI minimal; users define templates via the GUI.

The CLI imports `render_template` and uses it identically to the orchestrator. No GUI dialogs are invoked.

## Error handling & edge cases

| Scenario | Behavior |
|---|---|
| Active preset name doesn't match any preset | On config load: silently reset to first preset's name. |
| Template renders to empty string | Use the file stem (`fallback_filename`) instead. |
| iProperty access raises COM error | `get_iproperty` catches and returns `None`. |
| User cancels folder picker | `_on_export` returns without starting a worker, no log noise. |
| `prompt_folder_on_export=True` but config folder is empty | Picker starts at last-known folder, falling back to user home. |
| Two parts render to the same filename | Existing duplicate resolution (`_2`, `_3`) handles it unchanged. |
| Token references a name with `{` or `}` in it | Not supported — token regex is `\{[^{}]+\}`. Users won't have these in iProperty names. |

## Testing

**Unit tests** (no Inventor needed):

- `inventor_api/tests/test_document.py` — `get_iproperty` walks property sets, case-insensitive, returns `None` on miss.
- `inventor_export_tool/tests/test_templates.py` — render scenarios listed in §3.
- `inventor_export_tool/tests/test_config.py` — migration: missing `naming_presets` seeds default; orphaned `active_preset_name` is reset; round-trip JSON.
- `inventor_export_tool/tests/test_orchestrator.py` — given a mocked doc and a preset, `_build_export_items` produces the expected filenames.

**Manual GUI smoke test checklist** (cannot be automated — requires Inventor running):

- Open part → pick preset `OleM Default` → Run Export with empty folder field → folder picker appears → STEP + PDF produced with `{PartNumber} - {Description} - Rev{Revision Number}.ext` naming.
- Enable `[x] Prompt for folder on every export` → Run Export with folder set → picker still appears.
- Manage Presets → add a new preset, edit template, see live preview update → set active → cancel out → presets unchanged. Repeat with OK → presets saved.
- Preview button → scan-only output in log area, no export performed.
- Cancel during export → worker stops between files.

## Open questions

None.

## Rollout

Single PR. Existing user configs migrate automatically on first load. No external/breaking-change concerns — the tool is internal.
