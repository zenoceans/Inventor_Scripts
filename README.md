# Zabra-Cadabra

A multi-tab Windows desktop application for Autodesk Inventor 2026 automation. Built on a reusable Pythonic COM API wrapper, it bundles multiple engineering tools in a single `.exe` with a black-and-white minimalist UI.

**Current tools:**

| Tab | Description |
|---|---|
| **Inventor Export** | Batch-export STEP, DWG, and PDF from assemblies |
| **STEP Simplify** | Import STEP files, apply Inventor's Simplify feature, and save as `.ipt` |
| **Drawing Creation** | Batch-create IDW drawings with projected views and revision stamps |

---

## Features

### Inventor Export tab
- Connects to a running Inventor process via the COM API — no macro installation required
- Recursively walks the full assembly tree and deduplicates components by file path
- Optionally skips suppressed occurrences and Content Center parts
- Exports STEP (AP242), DWG, and PDF in a single pass
- Auto-discovers co-located `.idw` drawing files for DWG/PDF export
- DWG export uses Inventor's native `SaveAs` (no translator INI required)
- PDF export suppresses translator warning dialogs (e.g. font substitution) automatically
- Composes output filenames as `<PartName>-<Revision>.<ext>` (e.g. `Bracket-B.step`)
- Detects and resolves filename collisions with `_2`, `_3` suffixes
- GUI scan → preview → export workflow with live progress and per-file results
- Configurable translator options per format (STEP protocol, PDF resolution)

### STEP Simplify tab
- Batch import `.stp`/`.step` files into Inventor
- Apply Inventor's 3D Simplify feature (envelope replacement, feature removal, body filtering)
- Save simplified geometry as `.ipt` part files
- Set custom output name per file (double-click the Output Name column to edit)
- Optionally insert simplified parts into a target assembly
- Configurable simplify settings (envelope style, bounding type, feature removal levels)

### Drawing Creation tab
- Scans the active assembly tree for components missing co-located `.idw` drawings
- Creates new IDW drawings from a user-specified template
- Inserts projected views (base, top, right, iso) at configurable positions and scale
- Adds a revision table row with revision number, description, made-by, and approved-by
- Processes existing drawings too — applies revision stamps without re-creating them
- GUI scan → review → execute workflow with per-item include/exclude toggling
- Configurable scan depth, component filters, and view layout via settings dialog
- CLI standalone via `inventor-drawing` with all options as flags

### General
- Config persisted to `config.json`, `simplify_config.json`, and `drawing_config.json` between sessions
- Zen-branded header with logo
- Black-and-white minimalist theme

---

## Requirements

- Windows 10/11
- Autodesk Inventor 2026 (must be running before launching the tool)
- Python 3.10 or later (for development only — not needed for the `.exe`)
- `pywin32` (installed automatically via `uv sync`)

---

## Installation

```bash
git clone <repo-url>
cd Inventor_Scripts
uv sync --all-packages
```

---

## Usage

### From source

```bash
uv run zabra-cadabra             # Full GUI (all tools)
uv run inventor-export --help    # Export tool CLI
uv run inventor-simplify --help  # Simplify tool CLI
uv run inventor-drawing --help   # Drawing creation tool CLI
```

### From the `.exe`

Double-click `ZabraCadabra.exe`. See `usage_guide.txt` (bundled in the dist folder) for end-user instructions.

### Inventor Export workflow

1. **Configure** — Choose an output folder, select which export formats to produce (STEP, DWG, PDF), and set component filters (parts, sub-assemblies, top-level assembly, suppressed).
2. **Scan** — Click "Scan Assembly". The tool connects to Inventor, walks the active assembly tree, discovers all unique components and their co-located IDW drawings, and populates the preview table.
3. **Preview** — Review the table of planned output files. Each row shows the source component, the resolved output filename, and the export type.
4. **Export** — Click "Export". Files are written to the output folder. A progress bar advances per file, and each row is marked success or failure.

### STEP Simplify workflow

1. **Add files** — Click "Add Files..." and select one or more `.stp`/`.step` files.
2. **Set output names** — Double-click the Output Name column to rename any file. By default the STEP filename is used.
3. **Set output folder** — Click "Set Output Folder..." to choose where simplified `.ipt` files are saved.
4. **Assembly (optional)** — Check "Insert simplified .ipt into target assembly" and browse to a `.iam` file.
5. **Run** — Click "Run Simplify". Each file is imported, simplified, and saved. Progress is shown in the log.

### Drawing Creation workflow

1. **Template** — Set the drawing template path (`.idw` or `.dwt`) used for new drawings.
2. **Revision data** — Fill in revision number, description, made-by, and approved-by fields.
3. **Scan** — Click "Scan Assembly". The tool walks the active assembly tree and identifies components that are missing co-located `.idw` files.
4. **Review** — Toggle which items to include or exclude. Items with status "existing" will receive a revision stamp only; items with status "new" will get a new drawing created first.
5. **Execute** — Click "Execute". For each item: new drawings are created from the template with projected views, then a revision row is added. Progress and results are logged.
6. **Settings** — Click "Settings..." to configure view layout (positions, scale), scan depth, and post-processing options.

---

## Export Options

Translator-specific options are configured in `config.json` under the `export_options` key. Each format (`step`, `pdf`) has its own set of options that map directly to Inventor's translator add-in settings. Omit a format key or leave it as `{}` to use Inventor's built-in defaults.

> **Note:** DWG export uses Inventor's native `Document.SaveAs` rather than a translator add-in, so there are no configurable DWG translator options.

### Example `config.json`

```json
{
  "output_folder": "C:\\exports",
  "export_step": true,
  "export_dwg": true,
  "export_pdf": true,
  "include_parts": true,
  "include_subassemblies": true,
  "include_top_level": true,
  "include_suppressed": false,
  "export_options": {
    "step": {
      "ApplicationProtocolType": 3
    },
    "pdf": {
      "Vector_Resolution": 400,
      "All_Color_AS_Black": 0,
      "Remove_Line_Weights": 0
    }
  }
}
```

### STEP Options

Options for the STEP translator (`{90AF7F40-0C01-11D5-8E83-0010B541CD80}`).

| Option | Type | Values | Description |
|---|---|---|---|
| `ApplicationProtocolType` | `int` | `2` = AP 203 (Configuration Controlled Design), `3` = AP 214 (Automotive Design) | STEP application protocol. AP 214 is recommended for broad compatibility. AP 242 may be available on Inventor 2026 as the default when this option is omitted. |
| `Author` | `str` | Any text | Author field embedded in the STEP file header. |
| `Authorization` | `str` | Any text | Authorization field in the STEP file header. |
| `Description` | `str` | Any text | Description field in the STEP file header. |
| `Organization` | `str` | Any text | Organization field in the STEP file header. |

### PDF Options

Options for the PDF translator (`{0AC6FD96-2F4D-42CE-8BE0-8AEA580399E4}`). Used when exporting from IDW drawing files. Translator warning dialogs (e.g. font substitution popups) are suppressed automatically via `SilentOperation` so they don't block the batch flow.

| Option | Type | Values | Description |
|---|---|---|---|
| `Vector_Resolution` | `int` | DPI value (e.g. `200`, `400`, `720`) | Output resolution in dots per inch. Higher values produce sharper lines but larger files. Default is typically 400. |
| `All_Color_AS_Black` | `int` | `0` = preserve colors, `1` = all black | When set to `1`, all lines and text are rendered in black regardless of the drawing's color settings. |
| `Remove_Line_Weights` | `int` | `0` = keep line weights, `1` = remove | When set to `1`, all lines are rendered at uniform weight. |
| `Sheet_Range` | `int` | `0` = all sheets, `1` = custom range, `2` = current sheet | Which sheets of a multi-sheet drawing to include in the PDF. |
| `Custom_Begin_Sheet` | `int` | Sheet number (1-based) | First sheet to include when `Sheet_Range` is `1`. |
| `Custom_End_Sheet` | `int` | Sheet number (1-based) | Last sheet to include when `Sheet_Range` is `1`. |

### DWG Export

DWG export converts IDW drawings to DWG using Inventor's native `Document.SaveAs` method. This is more reliable than the DWG translator add-in for batch automation because it does not require an ACAD INI configuration file and works on documents opened invisibly (without triggering Vault checkout dialogs).

There are no user-configurable options for DWG export — Inventor uses its built-in defaults.

### Notes

- Option keys are **case-sensitive** and must match exactly as shown above.
- Available options may vary by Inventor version. Unrecognized options are silently ignored.
- These options correspond to what you see in Inventor's "Save Copy As" → "Options" dialog for each format.
- The option values are passed directly to the translator's `NameValueMap` after `HasSaveCopyAsOptions` populates the defaults, so any option not specified here retains the translator's default value.

---

## Architecture

This is a **uv workspace** with six packages. Each package has its own `pyproject.toml`, `src/` layout, and `tests/` directory.

```
Inventor_Scripts/
├── pyproject.toml                      # Workspace root — declares members
│
├── inventor_api/                       # Package: inventor-api (standalone library)
│   ├── pyproject.toml
│   ├── src/inventor_api/
│   │   ├── __init__.py                 # Public re-exports
│   │   ├── application.py             # InventorApp — connect, lifecycle
│   │   ├── document.py                # InventorDocument, AssemblyDocument, ComponentOccurrence
│   │   ├── properties.py              # iProperty access
│   │   ├── traversal.py               # walk_assembly — recursive tree walk
│   │   ├── exporters.py               # export_step, export_dwg, export_pdf, export_drawing
│   │   ├── importer.py                # import_step — STEP file import
│   │   ├── simplifier.py              # simplify_part, simplify_assembly, simplify_document
│   │   ├── types.py                   # Enums, constants (DocumentType, Simplify enums)
│   │   ├── exceptions.py              # InventorError hierarchy
│   │   └── _com_threading.py          # com_thread_scope context manager
│   └── tests/
│       ├── conftest.py
│       ├── test_document.py
│       ├── test_exporters.py
│       ├── test_importer.py
│       ├── test_simplifier.py
│       ├── test_traversal.py
│       └── test_types.py
│
├── inventor_utils/                     # Package: inventor-utils (shared utilities)
│   ├── pyproject.toml
│   ├── src/inventor_utils/
│   │   ├── __init__.py                 # Public re-exports
│   │   ├── filenames.py               # sanitize_filename, compose_filename, find_idw_path
│   │   ├── config.py                  # Generic config load/save helpers
│   │   ├── base_logger.py             # ToolLogger abstract base
│   │   ├── base_orchestrator.py       # BaseOrchestrator with callbacks
│   │   └── error_hints.py             # Human-readable error hints
│   └── tests/
│       ├── test_filenames.py
│       └── test_config.py
│
├── inventor_export_tool/               # Package: inventor-export-tool (CLI + GUI tab)
│   ├── pyproject.toml                  # Declares script: inventor-export
│   ├── src/inventor_export_tool/
│   │   ├── cli.py                     # inventor-export entry point
│   │   ├── gui.py                     # ExportToolGUI (ttk.Frame tab)
│   │   ├── models.py                  # ComponentInfo, ExportItem, ExportResult, ScanSummary
│   │   ├── config.py                  # AppConfig, load_config, save_config
│   │   ├── naming.py                  # Filename composition, IDW finding
│   │   ├── export_log.py              # Export run logging
│   │   ├── orchestrator.py            # Scan + export logic
│   │   └── settings_dialog.py         # Advanced export settings dialog
│   └── tests/
│       ├── test_config.py
│       ├── test_export_log.py
│       ├── test_models.py
│       ├── test_naming.py
│       └── test_settings_dialog.py
│
├── inventor_simplify_tool/             # Package: inventor-simplify-tool (CLI + GUI tab)
│   ├── pyproject.toml                  # Declares script: inventor-simplify
│   ├── src/inventor_simplify_tool/
│   │   ├── cli.py                     # inventor-simplify entry point
│   │   ├── gui.py                     # SimplifyToolGUI (ttk.Frame tab)
│   │   ├── models.py                  # SimplifyRow, SimplifyResult, SimplifySummary
│   │   ├── config.py                  # SimplifyConfig, load/save
│   │   ├── orchestrator.py            # Batch simplify logic
│   │   └── simplify_log.py            # Simplify run logging
│   └── tests/
│       ├── test_simplify_config.py
│       ├── test_simplify_log.py
│       └── test_simplify_models.py
│
├── inventor_drawing_tool/              # Package: inventor-drawing-tool (CLI + GUI tab)
│   ├── pyproject.toml                  # Declares script: inventor-drawing
│   ├── src/inventor_drawing_tool/
│   │   ├── cli.py                     # inventor-drawing entry point
│   │   ├── gui.py                     # DrawingToolGUI (ttk.Frame tab)
│   │   ├── models.py                  # DrawingItem, RevisionData, CreationSummary
│   │   ├── config.py                  # DrawingConfig, load/save
│   │   ├── scanner.py                 # Assembly scanning for drawings
│   │   ├── orchestrator.py            # Scan + create + revision logic
│   │   ├── creation_log.py            # Creation run logging
│   │   └── settings_dialog.py         # Advanced settings modal
│   └── tests/
│       ├── conftest.py
│       ├── test_config.py
│       ├── test_models.py
│       └── test_scanner.py
│
└── zabra_cadabra/                      # Package: zabra-cadabra (GUI shell)
    ├── pyproject.toml                  # Declares gui-script: zabra-cadabra
    ├── build.py                        # PyInstaller build script
    ├── src/zabra_cadabra/
    │   ├── app.py                     # main() — load configs, create shell, mainloop
    │   ├── shell.py                   # ZabraApp — Tk root, header, Notebook, theme
    │   ├── theme.py                   # apply_bw_theme() — black/white ttk.Style
    │   └── tab_registry.py            # TabSpec + TABS list
    └── tests/
```

### Package dependencies

```
inventor-api           (no workspace deps)
inventor-utils         (no workspace deps — pure Python)
inventor-export-tool   -> inventor-api
inventor-simplify-tool -> inventor-api
inventor-drawing-tool  -> inventor-api, inventor-utils
zabra-cadabra          -> inventor-export-tool, inventor-simplify-tool, inventor-drawing-tool
```

### Architecture boundaries

- **`inventor_api`**: Pythonic COM wrapper. Returns its own types. No imports from application packages.
- **`inventor_utils`**: Shared pure-Python utilities (filenames, config, base logger, base orchestrator, error hints). No GUI, no COM, no `inventor_api` imports.
- **`inventor_export_tool`**: Export tab logic. Imports from `inventor_api`. No dependency on other tool packages.
- **`inventor_simplify_tool`**: Simplify tab logic. Imports from `inventor_api`. No dependency on other tool packages.
- **`inventor_drawing_tool`**: Drawing creation tab logic. Imports from `inventor_api` and `inventor_utils`. No dependency on other tool packages.
- **`zabra_cadabra`**: Shell application. Imports tab factories from all tool packages.
- **GUI** modules (`gui.py`): No direct COM or `inventor_api` calls — go through orchestrators on background threads.

### Adding a new tab

1. Create a new workspace package `inventor_<tool_name>/` with `src/`, `tests/`, and `pyproject.toml` declaring `inventor-api` and `inventor-utils` as dependencies.
2. Add a `gui.py` exposing a `ttk.Frame` subclass with `start_polling()` and `close()` methods.
3. Add the package to `[tool.uv.workspace] members` in the root `pyproject.toml`.
4. Add a factory function and `TabSpec` entry in `zabra_cadabra/src/zabra_cadabra/tab_registry.py`.
5. Add the new package as a dependency in `zabra_cadabra/pyproject.toml`.

---

## `inventor_api` API Reference

### `inventor_api.application` — Application connection

#### `class InventorApp`

Pythonic wrapper around the `Inventor.Application` COM object.

```python
InventorApp(com_app: object) -> None
```

| Member | Signature | Description |
|---|---|---|
| `connect` | `classmethod connect() -> InventorApp` | Connect to a running Inventor instance. Raises `InventorNotRunningError` if Inventor is not running. |
| `is_running` | `staticmethod is_running() -> bool` | Return `True` if a running Inventor instance can be found via COM. |
| `com_app` | `property -> object` | The underlying `Inventor.Application` COM object. |
| `active_document` | `property -> InventorDocument` | Currently active document. Returns `AssemblyDocument` when the active doc is an assembly. Raises `InventorError` if no document is open. |
| `get_active_assembly` | `get_active_assembly() -> AssemblyDocument` | Like `active_document` but asserts the result is an assembly. Raises `InventorNotAssemblyError` otherwise. |
| `open_document` | `open_document(path: str, visible: bool = False) -> InventorDocument` | Open a document from disk. `visible=False` opens without creating a window. Raises `DocumentOpenError` on failure. |

---

### `inventor_api.document` — Document wrappers

#### `class InventorDocument`

Wraps an Inventor document COM object (`.ipt`, `.iam`, `.idw`, etc.).

```python
InventorDocument(com_doc: object) -> None
```

| Member | Signature | Description |
|---|---|---|
| `com_object` | `property -> object` | The underlying COM document object. |
| `full_path` | `property -> str` | Full file path of the document. |
| `display_name` | `property -> str` | Filename without path or extension. |
| `document_type` | `property -> DocumentType` | Document type as a `DocumentType` enum member. |
| `is_content_center` | `property -> bool` | `True` if the path contains `"content center files"`. |
| `get_property` | `get_property(prop_set_name: str, prop_name: str) -> str \| None` | Read a single iProperty value by property set name and property name. Returns `None` if missing or empty. |
| `get_revision` | `get_revision() -> str` | Read `"Revision Number"` from Design Tracking Properties. Returns `"NoRev"` if absent. |
| `close` | `close(skip_save: bool = True) -> None` | Close the document. Raises `InventorError` on failure. |

#### `class AssemblyDocument(InventorDocument)`

Extends `InventorDocument` with assembly-specific traversal.

| Member | Signature | Description |
|---|---|---|
| `occurrences` | `property -> Iterator[ComponentOccurrence]` | Iterate over top-level component occurrences. |

#### `class ComponentOccurrence`

Wraps a single component occurrence inside an assembly.

```python
ComponentOccurrence(com_occurrence: object) -> None
```

| Member | Signature | Description |
|---|---|---|
| `referenced_document` | `property -> InventorDocument` | The document this occurrence references. Returns `AssemblyDocument` for sub-assemblies. |
| `is_suppressed` | `property -> bool` | `True` if this occurrence is suppressed. |
| `definition_document_type` | `property -> DocumentType` | Document type of the referenced component. |

---

### `inventor_api.traversal` — Assembly tree traversal

#### `@dataclass DiscoveredComponent`

```python
@dataclass
class DiscoveredComponent:
    document: InventorDocument
    is_top_level: bool = False
    is_suppressed: bool = False
```

#### `walk_assembly`

```python
def walk_assembly(
    assembly: AssemblyDocument,
    *,
    include_suppressed: bool = False,
    include_content_center: bool = False,
) -> list[DiscoveredComponent]
```

Recursively walk an assembly tree and return all discovered components. The root assembly is included first with `is_top_level=True`. Duplicate documents (same file path) are visited only once. Sub-assemblies are recursed into automatically.

---

### `inventor_api.exporters` — Format export functions

All export functions raise `ExportError` on failure. `TranslatorError` (a subclass of `ExportError`) is raised when the required translator add-in cannot be found.

#### `export_step`

```python
def export_step(
    app: InventorApp,
    document: InventorDocument,
    output_path: str | Path,
    options: dict[str, Any] | None = None,
) -> None
```

Export a part or assembly to STEP format (AP242 on Inventor 2026). The output directory is created if it does not exist. Pass `options` to override translator defaults (see [STEP Options](#step-options)).

#### `export_pdf`

```python
def export_pdf(
    app: InventorApp,
    drawing: InventorDocument,
    output_path: str | Path,
    options: dict[str, Any] | None = None,
) -> None
```

Export a drawing document (`.idw`) to PDF format. Translator warning dialogs are suppressed via `SilentOperation`. Pass `options` to override translator defaults (see [PDF Options](#pdf-options)).

#### `export_drawing`

```python
def export_drawing(
    app: InventorApp,
    idw_path: str,
    output_path: str | Path,
    fmt: str,
    options: dict[str, Any] | None = None,
) -> None
```

Open an `.idw` file, export it, then close it (only if it was not already open before this call).

| Parameter | Description |
|---|---|
| `idw_path` | Path to the `.idw` source file. |
| `output_path` | Full path for the output file. |
| `fmt` | `"dwg"` or `"pdf"`. Raises `ValueError` for other values. |
| `options` | Translator option overrides (PDF only — DWG uses native SaveAs). |

For DWG format, uses `Document.SaveAs` (Inventor's native DWG support) instead of the translator add-in. For PDF format, uses the translator add-in pipeline. IDW documents are opened invisibly to avoid Vault checkout dialogs.

Raises `DocumentOpenError` if the IDW cannot be opened, `ExportError` if the export fails.

---

### `inventor_api.importer` — STEP file import

#### `import_step`

```python
def import_step(
    app: InventorApp,
    step_path: str | Path,
    *,
    visible: bool = True,
) -> InventorDocument
```

Open a STEP file in Inventor using the native STEP translator. Inventor auto-detects STEP format from the file extension. The result is either a `PartDocument` or `AssemblyDocument` depending on the STEP content.

Returns `AssemblyDocument` for assemblies, `InventorDocument` for parts. Raises `StepImportError` if the file does not exist or cannot be opened.

#### `is_assembly_document`

```python
def is_assembly_document(doc: InventorDocument) -> bool
```

Return `True` if the document is an assembly (`.iam`).

---

### `inventor_api.simplifier` — Simplify feature

#### `@dataclass SimplifySettings`

Settings passed to the Simplify COM API. All enum fields use the `IntEnum` types from `inventor_api.types`. Fields left as `None` are skipped — Inventor uses its own defaults.

```python
@dataclass
class SimplifySettings:
    envelope_style: SimplifyEnvelopeStyle | None = None
    bounding_type: SimplifyBoundingType | None = None
    remove_internal_bodies: bool | None = None
    remove_bodies_by_size: bool | None = None
    remove_bodies_size_cm: float | None = None
    remove_holes: SimplifyFeatureRemoval | None = None
    remove_fillets: SimplifyFeatureRemoval | None = None
    remove_chamfers: SimplifyFeatureRemoval | None = None
    remove_pockets: SimplifyFeatureRemoval | None = None
    remove_embosses: SimplifyFeatureRemoval | None = None
    remove_tunnels: SimplifyFeatureRemoval | None = None
    output_style: SimplifyOutputStyle | None = None
    raw_options: dict[str, Any] = field(default_factory=dict)
```

The `raw_options` dict allows setting arbitrary COM properties by name, for properties not yet enumerated.

#### `simplify_document`

```python
def simplify_document(
    app: InventorApp,
    doc: InventorDocument,
    output_path: str | Path,
    settings: SimplifySettings,
) -> InventorDocument
```

Primary entry point. Dispatches to `simplify_part` or `simplify_assembly` based on document type. Returns the saved output `.ipt`, left open in Inventor.

#### `simplify_part`

```python
def simplify_part(
    app: InventorApp,
    doc: InventorDocument,
    output_path: str | Path,
    settings: SimplifySettings,
) -> InventorDocument
```

Apply Simplify to a Part document in-place and SaveAs to `output_path`. Raises `SimplifyError` if the simplify feature fails, `SaveAsError` if SaveAs fails.

#### `simplify_assembly`

```python
def simplify_assembly(
    app: InventorApp,
    doc: AssemblyDocument,
    output_path: str | Path,
    settings: SimplifySettings,
) -> InventorDocument
```

Apply Assembly Simplify to an `.iam`, producing a new derived `.ipt`. The original assembly is closed without saving. Raises `SimplifyError` or `SaveAsError`.

---

### `inventor_api.types` — Constants and enumerations

#### `class DocumentType(IntEnum)`

```python
class DocumentType(IntEnum):
    PART     = 12290  # .ipt
    ASSEMBLY = 12291  # .iam
    DRAWING  = 12292  # .idw
```

#### `class TranslatorId(str, Enum)`

GUIDs for Inventor translator add-ins.

```python
class TranslatorId(str, Enum):
    STEP = "{90AF7F40-0C01-11D5-8E83-0010B541CD80}"
    DWG  = "{C24E3AC4-122E-11D5-8E91-0010B541CD80}"
    PDF  = "{0AC6FD96-2F4D-42CE-8BE0-8AEA580399E4}"
    IGES = "{90AF7F40-0C01-11D5-8E83-0010B541CD80}"
    SAT  = "{89162634-0C01-11D5-8E83-0010B541CD80}"
    STL  = "{533E9A98-FC3B-11D4-8E7E-0010B541CD80}"
```

#### `class PropertySet(str, Enum)`

Standard Inventor iProperty set names.

```python
class PropertySet(str, Enum):
    SUMMARY          = "Inventor Summary Information"
    DOCUMENT_SUMMARY = "Inventor Document Summary Information"
    DESIGN_TRACKING  = "Design Tracking Properties"
    USER_DEFINED     = "Inventor User Defined Properties"
```

#### Simplify enumerations

```python
class SimplifyEnvelopeStyle(IntEnum):
    NONE = 0, WHOLE_PART = 1, EACH_BODY = 2, SELECTED_BODIES = 3

class SimplifyBoundingType(IntEnum):
    ORTHOGONAL = 0, ORIENTED_MIN_BB = 1, ORIENTED_MIN_CYLINDER = 2

class SimplifyFeatureRemoval(IntEnum):
    NONE = 0, ALL = 1, BY_RANGE = 2

class SimplifyOutputStyle(IntEnum):
    SINGLE_SOLID_NO_SEAMS = 0, SINGLE_SOLID_WITH_SEAMS = 1,
    MAINTAIN_EACH_SOLID = 2, SINGLE_COMPOSITE = 3
```

#### `IO_MECHANISM`

```python
IO_MECHANISM: int = 13059  # kFileBrowseIOMechanism
```

---

### `inventor_api.exceptions` — Exception hierarchy

```
InventorError
├── InventorNotRunningError     # Inventor not running or COM not reachable
├── InventorNotAssemblyError    # Active document is not an assembly
├── DocumentOpenError           # Failed to open a document
│       .path: str
│       .cause: Exception | None
├── ExportError                 # Failed to export a document
│       .path: str
│       .format: str
│       .cause: Exception | None
│   └── TranslatorError         # Translator add-in not found
├── StepImportError             # Failed to import a STEP file
│       .path: str
│       .cause: Exception | None
├── SimplifyError               # Failed to simplify a document
│       .path: str
│       .cause: Exception | None
└── SaveAsError                 # Failed to save a document
        .path: str
        .cause: Exception | None
```

---

### `inventor_api._com_threading` — COM threading

#### `com_thread_scope`

```python
@contextmanager
def com_thread_scope() -> Generator[None, None, None]
```

Initialize COM for the current thread and clean up on exit. Required when calling Inventor COM from a non-main thread (e.g., a GUI background worker).

```python
from inventor_api._com_threading import com_thread_scope

with com_thread_scope():
    app = InventorApp.connect()
    # ... COM work ...
```

---

## `inventor_export_tool` API Reference

### `inventor_export_tool.models` — Data models

#### `@dataclass ComponentInfo`

```python
@dataclass
class ComponentInfo:
    source_path: str
    display_name: str
    document_type: str          # "part" | "assembly"
    revision: str               # "NoRev" if empty
    is_top_level: bool = False
    idw_path: str | None = None
    is_content_center: bool = False
    is_suppressed: bool = False
```

#### `@dataclass ExportItem`

```python
@dataclass
class ExportItem:
    component: ComponentInfo
    export_type: str            # "step" | "dwg" | "pdf"
    output_filename: str
    output_path: str
```

#### `@dataclass ExportResult`

```python
@dataclass
class ExportResult:
    item: ExportItem
    success: bool
    error_message: str | None = None
    duration_seconds: float = 0.0
```

#### `@dataclass ScanSummary`

```python
@dataclass
class ScanSummary:
    total_components: int
    content_center_excluded: int
    suppressed_excluded: int
    export_items: list[ExportItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

---

### `inventor_export_tool.config` — Configuration persistence

#### `@dataclass AppConfig`

```python
@dataclass
class AppConfig:
    output_folder: str = ""
    export_step: bool = True
    export_dwg: bool = True
    export_pdf: bool = True
    include_parts: bool = True
    include_subassemblies: bool = True
    include_top_level: bool = True
    include_suppressed: bool = False
    export_options: dict[str, dict[str, Any]] = field(default_factory=dict)
```

The `export_options` field holds per-format translator settings. See [Export Options](#export-options) for the full reference.

#### `load_config` / `save_config`

```python
def load_config(path: Path | None = None) -> AppConfig
def save_config(config: AppConfig, path: Path | None = None) -> None
```

---

### `inventor_export_tool.naming` — Filename composition

#### `sanitize_filename`

```python
def sanitize_filename(name: str) -> str
```

Remove or replace characters that are invalid in Windows filenames.

#### `compose_filename`

```python
def compose_filename(display_name: str, revision: str, extension: str) -> str
```

Compose an export filename: `compose_filename("Bracket", "B", "step")` → `"Bracket-B.step"`. Empty revision becomes `"NoRev"`.

#### `find_idw_path`

```python
def find_idw_path(source_path: str) -> str | None
```

Find the co-located `.idw` file for a given `.ipt` or `.iam` file.

#### `resolve_duplicates`

```python
def resolve_duplicates(items: list[ExportItem]) -> list[ExportItem]
```

Detect output filename collisions and append `_2`, `_3`, ... suffixes to conflicting items.

---

## `inventor_simplify_tool` API Reference

### `inventor_simplify_tool.models` — Data models

#### `@dataclass SimplifyRow`

```python
@dataclass
class SimplifyRow:
    step_path: str            # Absolute path to the .stp/.step file
    output_filename: str      # Desired output filename (without .ipt extension)
    output_folder: str        # Destination folder for the simplified .ipt
```

#### `@dataclass SimplifyResult`

```python
@dataclass
class SimplifyResult:
    row: SimplifyRow
    success: bool
    output_path: str | None = None
    imported_as_assembly: bool = False
    error_message: str | None = None
    duration_seconds: float = 0.0
```

#### `@dataclass SimplifySummary`

```python
@dataclass
class SimplifySummary:
    total_rows: int
    succeeded: int
    failed: int
    results: list[SimplifyResult] = field(default_factory=list)
```

### `inventor_simplify_tool.config` — Configuration persistence

#### `@dataclass SimplifyConfig`

```python
@dataclass
class SimplifyConfig:
    simplify_settings: dict[str, Any] = field(default_factory=dict)
    target_assembly_path: str = ""
    add_to_assembly: bool = False
```

Persisted to `simplify_config.json` next to the executable.

#### `load_simplify_config` / `save_simplify_config`

```python
def load_simplify_config(path: Path | None = None) -> SimplifyConfig
def save_simplify_config(config: SimplifyConfig, path: Path | None = None) -> None
```

---

## `inventor_drawing_tool` API Reference

### `inventor_drawing_tool.models` — Data models

#### `class DrawingStatus(str, Enum)`

```python
class DrawingStatus(str, Enum):
    EXISTING = "existing"
    NEEDS_CREATION = "new"
```

#### `@dataclass DrawingItem`

```python
@dataclass
class DrawingItem:
    part_path: str
    part_name: str
    drawing_path: str | None
    drawing_status: DrawingStatus
    document_type: str          # "part" | "assembly"
    depth: int
    include: bool = True
```

#### `@dataclass RevisionData`

```python
@dataclass
class RevisionData:
    rev_number: str = ""
    rev_description: str = ""
    made_by: str = ""
    approved_by: str = ""
```

#### `@dataclass ScanResult`

```python
@dataclass
class ScanResult:
    assembly_path: str
    items: list[DrawingItem]
    total_parts: int
    parts_with_drawings: int
    parts_without_drawings: int
    content_center_excluded: int
    warnings: list[str]
```

#### `@dataclass CreationItemResult`

```python
@dataclass
class CreationItemResult:
    item: DrawingItem
    success: bool
    action: str                 # "created+revision" | "revision_only" | "skipped" | "failed"
    error_message: str | None
    duration_seconds: float
```

#### `@dataclass CreationSummary`

```python
@dataclass
class CreationSummary:
    total: int
    created: int
    revised: int
    failed: int
    results: list[CreationItemResult]
```

---

### `inventor_drawing_tool.config` — Configuration persistence

#### `@dataclass DrawingConfig`

```python
@dataclass
class DrawingConfig:
    # Template
    template_path: str = ""

    # Scan filters
    include_parts: bool = True
    include_subassemblies: bool = False
    include_suppressed: bool = False
    include_content_center: bool = False
    max_depth: int | None = None        # None = unlimited

    # Drawing creation
    auto_create_drawings: bool = True
    default_scale: float = 1.0
    insert_base_view: bool = True
    insert_top_view: bool = True
    insert_right_view: bool = False
    insert_iso_view: bool = True
    base_view_x: float = 15.0
    base_view_y: float = 15.0
    top_view_offset_y: float = 12.0
    right_view_offset_x: float = 15.0
    iso_view_x: float = 32.0
    iso_view_y: float = 25.0

    # Revision memory
    last_rev_number: str = ""
    last_rev_description: str = ""
    last_made_by: str = ""
    last_approved_by: str = ""

    # Advanced
    save_after_revision: bool = True
    close_after_processing: bool = True
```

Persisted to `drawing_config.json` next to the executable.

#### `load_drawing_config` / `save_drawing_config`

```python
def load_drawing_config(path: Path | None = None) -> DrawingConfig
def save_drawing_config(config: DrawingConfig, path: Path | None = None) -> None
```

---

### `inventor_drawing_tool.scanner` — Assembly scanning

#### `scan_assembly_for_creation`

```python
def scan_assembly_for_creation(app: InventorApp, config: DrawingConfig) -> ScanResult
```

Walk the active assembly tree and identify components that need drawings created. For each component, checks for a co-located `.idw` file to determine `DrawingStatus.EXISTING` vs `NEEDS_CREATION`. Respects config filters (parts, sub-assemblies, suppressed, content center, max depth).

---

### `inventor_drawing_tool.orchestrator` — Creation orchestrator

#### `class DrawingCreationOrchestrator(BaseOrchestrator)`

```python
DrawingCreationOrchestrator(
    config: DrawingConfig,
    revision_data: RevisionData,
    progress_callback: ProgressCallback | None = None,
    log_callback: LogCallback | None = None,
)
```

| Member | Signature | Description |
|---|---|---|
| `scan` | `scan() -> ScanResult` | Connect to Inventor and scan the active assembly. |
| `execute` | `execute(items: list[DrawingItem], cancel_event: Event \| None = None) -> CreationSummary` | Process items: create drawings where needed, apply revision stamps. |
| `last_log_path` | `property -> Path \| None` | Path to the creation log file after execution. |

**Per-item processing:**
- `NEEDS_CREATION` + `auto_create_drawings=True`: Create drawing from template, insert views, add revision row → `"created+revision"`
- `EXISTING`: Open drawing, add revision row → `"revision_only"`
- `NEEDS_CREATION` + `auto_create_drawings=False`: → `"skipped"`

---

## `inventor_utils` API Reference

### `inventor_utils.filenames` — Filename utilities

```python
def sanitize_filename(name: str) -> str
def compose_filename(display_name: str, revision: str, extension: str) -> str
def find_idw_path(source_path: str) -> str | None
def is_content_center_path(file_path: str) -> bool
```

### `inventor_utils.config` — Generic config helpers

```python
def get_config_path(filename: str) -> Path
def load_dataclass_config(cls: type[T], path: Path) -> T
def save_dataclass_config(config: Any, path: Path) -> None
```

### `inventor_utils.base_logger` — Abstract logging base

```python
class ToolLogger(ABC):
    def __init__(self, output_folder: str | Path, prefix: str) -> None: ...
    log_path: Path | None       # property
    def open(self) -> None: ...
    def close(self) -> None: ...
    @abstractmethod def log_start(self, *args, **kwargs) -> None: ...
    @abstractmethod def log_finish(self, *args, **kwargs) -> None: ...
```

### `inventor_utils.base_orchestrator` — Base orchestrator

```python
ProgressCallback = Callable[[int, int], None]   # (current, total)
LogCallback = Callable[[str], None]

class BaseOrchestrator:
    def __init__(
        self,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None: ...
```

### `inventor_utils.error_hints` — Error hints

```python
def error_hint(error_message: str) -> str
```

Returns a human-readable hint for known error patterns (missing revision table, COM errors, file-not-found, etc.), or `""` if unrecognized.

---

## Building a Standalone Executable

```bash
uv sync --all-packages     # Install dependencies including PyInstaller
cd zabra_cadabra && uv run python build.py
```

This produces a `dist/ZabraCadabra/` folder containing:
- `ZabraCadabra.exe` — the application
- `_internal/` — supporting DLLs, libraries, and the Zen logo
- `usage_guide.txt` — instructions for end users

**To distribute:** Zip the entire `dist/ZabraCadabra/` folder and send it. The recipient unzips and double-clicks the `.exe`. No Python or other tools required — only Inventor.

---

## Development

```bash
# Clone and install
git clone <repo-url>
cd Inventor_Scripts
uv sync --all-packages

# Run the app
uv run zabra-cadabra

# Run tests (per package)
uv run --package inventor-api pytest
uv run --package inventor-utils pytest
uv run --package inventor-export-tool pytest
uv run --package inventor-simplify-tool pytest
uv run --package inventor-drawing-tool pytest
uv run --package zabra-cadabra pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run ty check
```

---

## License

Internal tool — not licensed for external distribution.
