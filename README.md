# Inventor Export Tool

A Windows desktop utility that connects to a running Autodesk Inventor 2026 instance via COM, scans the active assembly tree, and batch-exports every unique component and drawing to STEP, DWG, and/or PDF. A Tkinter GUI lets you configure output options, preview exactly which files will be written (with resolved filenames), and then run the export with a live progress display.

---

## Features

- Connects to a running Inventor process via the COM API — no macro installation required
- Recursively walks the full assembly tree and deduplicates components by file path
- Optionally skips suppressed occurrences and Content Center parts
- Exports STEP (AP242), DWG, and PDF in a single pass
- Auto-discovers co-located `.idw` drawing files for DWG/PDF export
- Composes output filenames as `<PartName>-<Revision>.<ext>` (e.g. `Bracket-B.step`)
- Detects and resolves filename collisions with `_2`, `_3` suffixes
- GUI scan → preview → export workflow with live progress and per-file results
- Config persisted to `config.json` between sessions
- Configurable translator options per format (STEP protocol, PDF resolution, DWG settings)

---

## Requirements

- Windows 10/11
- Autodesk Inventor 2026 (must be running before launching the tool)
- Python 3.10 or later
- `pywin32` (installed automatically via `uv sync`)

---

## Installation

```
git clone <repo-url>
cd Inventor_Scripts
uv sync
```

---

## Usage

```
uv run python -m inventor_export_tool
```

**GUI workflow:**

1. **Configure** — Choose an output folder, select which export formats to produce (STEP, DWG, PDF), and set component filters (parts, sub-assemblies, top-level assembly, suppressed).
2. **Scan** — Click "Scan Assembly". The tool connects to Inventor, walks the active assembly tree, discovers all unique components and their co-located IDW drawings, and populates the preview table. No files are written at this stage.
3. **Preview** — Review the table of planned output files. Each row shows the source component, the resolved output filename, and the export type. Collisions are resolved before you see the list.
4. **Export** — Click "Export". Files are written to the output folder. A progress bar advances per file, and each row is marked success or failure. A summary is shown on completion.

---

## Export Options

Translator-specific options are configured in `config.json` under the `export_options` key. Each format (`step`, `pdf`, `dwg`) has its own set of options that map directly to Inventor's translator add-in settings. Omit a format key or leave it as `{}` to use Inventor's built-in defaults.

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
    },
    "dwg": {}
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

Options for the PDF translator (`{0AC6FD96-2F4D-42CE-8BE0-8AEA580399E4}`). Used when exporting from IDW drawing files.

| Option | Type | Values | Description |
|---|---|---|---|
| `Vector_Resolution` | `int` | DPI value (e.g. `200`, `400`, `720`) | Output resolution in dots per inch. Higher values produce sharper lines but larger files. Default is typically 400. |
| `All_Color_AS_Black` | `int` | `0` = preserve colors, `1` = all black | When set to `1`, all lines and text are rendered in black regardless of the drawing's color settings. |
| `Remove_Line_Weights` | `int` | `0` = keep line weights, `1` = remove | When set to `1`, all lines are rendered at uniform weight. |
| `Sheet_Range` | `int` | `0` = all sheets, `1` = custom range, `2` = current sheet | Which sheets of a multi-sheet drawing to include in the PDF. |
| `Custom_Begin_Sheet` | `int` | Sheet number (1-based) | First sheet to include when `Sheet_Range` is `1`. |
| `Custom_End_Sheet` | `int` | Sheet number (1-based) | Last sheet to include when `Sheet_Range` is `1`. |

### DWG Options

Options for the DWG translator (`{C24E3AC4-122E-11D5-8E91-0010B541CD80}`). Used when exporting from IDW drawing files.

| Option | Type | Values | Description |
|---|---|---|---|
| `Export_Acad_IniFile` | `str` | File path | Path to an `.ini` file containing DWG export settings. Create this file by opening Inventor's "Save Copy As" dialog for DWG format, configuring settings, and clicking "Save Configuration". |

### Notes

- Option keys are **case-sensitive** and must match exactly as shown above.
- Available options may vary by Inventor version. Unrecognized options are silently ignored.
- These options correspond to what you see in Inventor's "Save Copy As" → "Options" dialog for each format.
- The option values are passed directly to the translator's `NameValueMap` after `HasSaveCopyAsOptions` populates the defaults, so any option not specified here retains the translator's default value.

---

## Architecture

```
Inventor_Scripts/
├── inventor_api/               # Low-level COM wrapper (reusable library)
│   ├── __init__.py             # Public re-exports
│   ├── application.py          # InventorApp — connect, open docs, active doc
│   ├── document.py             # InventorDocument, AssemblyDocument, ComponentOccurrence
│   ├── traversal.py            # walk_assembly — recursive tree walk
│   ├── exporters.py            # export_step, export_dwg, export_pdf, export_drawing
│   ├── types.py                # DocumentType, TranslatorId, PropertySet enums
│   ├── exceptions.py           # InventorError hierarchy
│   └── _com_threading.py       # com_thread_scope context manager
│
└── inventor_export_tool/       # Application layer (GUI + orchestration)
    ├── __main__.py             # Entry point
    ├── models.py               # ComponentInfo, ExportItem, ExportResult, ScanSummary
    ├── config.py               # AppConfig, load_config, save_config
    ├── naming.py               # compose_filename, find_idw_path, resolve_duplicates
    ├── export_log.py           # Export run logging
    └── gui/                    # Tkinter GUI components
```

`inventor_api` has no dependency on `inventor_export_tool`. The application layer imports `inventor_api` to perform COM operations and maps results onto its own model types.

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

A component found during assembly traversal.

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

| Parameter | Default | Description |
|---|---|---|
| `assembly` | — | Root assembly to traverse. |
| `include_suppressed` | `False` | Include suppressed occurrences. |
| `include_content_center` | `False` | Include Content Center parts. |

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

#### `export_dwg`

```python
def export_dwg(
    app: InventorApp,
    drawing: InventorDocument,
    output_path: str | Path,
    options: dict[str, Any] | None = None,
) -> None
```

Export a drawing document (`.idw`) to DWG format. Pass `options` to override translator defaults (see [DWG Options](#dwg-options)).

#### `export_pdf`

```python
def export_pdf(
    app: InventorApp,
    drawing: InventorDocument,
    output_path: str | Path,
    options: dict[str, Any] | None = None,
) -> None
```

Export a drawing document (`.idw`) to PDF format. Pass `options` to override translator defaults (see [PDF Options](#pdf-options)).

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
| `options` | Translator option overrides. See [Export Options](#export-options). |

Raises `DocumentOpenError` if the IDW cannot be opened, `ExportError` if the export fails.

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

GUIDs for Inventor translator add-ins used by the export functions.

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

#### `IO_MECHANISM`

```python
IO_MECHANISM: int = 13059  # kFileBrowseIOMechanism
```

Used when setting `TranslationContext.Type` on the COM translation context.

---

### `inventor_api.exceptions` — Exception hierarchy

```
InventorError
├── InventorNotRunningError     # Inventor not running or COM not reachable
├── InventorNotAssemblyError    # Active document is not an assembly
├── DocumentOpenError           # Failed to open a document
│       .path: str
│       .cause: Exception | None
└── ExportError                 # Failed to export a document
        .path: str
        .format: str
        .cause: Exception | None
    └── TranslatorError         # Translator add-in not found
```

#### `DocumentOpenError`

```python
DocumentOpenError(path: str, cause: Exception | None = None)
```

#### `ExportError`

```python
ExportError(path: str, format: str, cause: Exception | None = None)
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

A discovered component in the assembly tree.

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

A single file to be exported.

```python
@dataclass
class ExportItem:
    component: ComponentInfo
    export_type: str            # "step" | "dwg" | "pdf"
    output_filename: str
    output_path: str
```

#### `@dataclass ExportResult`

Result of exporting one item.

```python
@dataclass
class ExportResult:
    item: ExportItem
    success: bool
    error_message: str | None = None
    duration_seconds: float = 0.0
```

#### `@dataclass ScanSummary`

Summary produced by a dry-run scan.

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

User-configurable settings persisted to `config.json`.

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

#### `get_config_path`

```python
def get_config_path() -> Path
```

Return path to `config.json` next to the main script or PyInstaller executable.

#### `load_config`

```python
def load_config(path: Path | None = None) -> AppConfig
```

Load config from a JSON file. Returns an `AppConfig` with defaults if the file is missing or corrupt. Unknown keys are silently ignored.

#### `save_config`

```python
def save_config(config: AppConfig, path: Path | None = None) -> None
```

Serialize `config` to JSON and write it to disk.

---

### `inventor_export_tool.naming` — Filename composition

#### `sanitize_filename`

```python
def sanitize_filename(name: str) -> str
```

Remove or replace characters that are invalid in Windows filenames (`< > : " / \ | ? *` and control characters). Trailing dots and spaces are stripped. Returns `"_"` if the result would be empty.

#### `compose_filename`

```python
def compose_filename(display_name: str, revision: str, extension: str) -> str
```

Compose an export filename from its parts.

```
compose_filename("Bracket", "B", "step")  ->  "Bracket-B.step"
compose_filename("Plate", "", "dwg")      ->  "Plate-NoRev.dwg"
```

An empty or whitespace-only `revision` is replaced with `"NoRev"`. `extension` must not include the leading dot.

#### `find_idw_path`

```python
def find_idw_path(source_path: str) -> str | None
```

Find the co-located `.idw` file for a given `.ipt` or `.iam` file. Checks both `.idw` and `.IDW`. Returns `None` if no drawing file exists.

#### `is_content_center_path`

```python
def is_content_center_path(file_path: str) -> bool
```

Return `True` if `file_path` contains `"content center files"` (case-insensitive).

#### `resolve_duplicates`

```python
def resolve_duplicates(items: list[ExportItem]) -> list[ExportItem]
```

Detect output filename collisions across a list of `ExportItem` objects and append `_2`, `_3`, … suffixes to conflicting items. Mutates `output_filename` and `output_path` on affected items and returns the same list.

---

## Building a Standalone Executable

To create a standalone `.exe` that can be distributed to users without Python:

```bash
uv sync            # Install dependencies including PyInstaller
uv run python build.py
```

This produces a `dist/InventorExportTool/` folder containing:
- `InventorExportTool.exe` — the application
- `usage_guide.txt` — instructions for end users
- Supporting DLLs and libraries

**To distribute:** Zip the entire `dist/InventorExportTool/` folder and send it. The recipient unzips and double-clicks the `.exe`. No Python or other tools required — only Inventor.

---

## Development

```bash
# Clone and install
git clone <repo-url>
cd Inventor_Scripts
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .
```

---

## License

Internal tool — not licensed for external distribution.
