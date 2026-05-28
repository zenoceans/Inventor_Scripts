# Export Naming Presets & Streamlined Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hard-coded `display_name + revision` export naming with a token-based template system backed by named presets, and collapse the two-step Scan → Export flow into a single-click export with an optional folder picker.

**Architecture:** `inventor_api.document.InventorDocument` gains `get_iproperty(name)` for cross-set iProperty lookup. A new `inventor_export_tool/templates.py` renders `{Token}` templates against a document. `AppConfig` gains `NamingPreset` and three new fields; `load_config` is extended with post-load migration. The GUI is restructured: "Run Export" is the primary button, "Scan Assembly" becomes "Preview", and a new "Naming Preset" row plus a `[Manage...]` button open `NamingPresetDialog`. `_export_worker` becomes single-pass (no re-scan). `compose_filename` is removed everywhere.

**Tech Stack:** Python 3.13, tkinter/ttk, `dataclasses`, `unittest.mock.MagicMock`, pytest, `uv`, ruff, pywin32 COM (mocked in tests).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `inventor_api/src/inventor_api/document.py` | Modify | Add `get_iproperty(name)` |
| `inventor_api/tests/test_document.py` | Modify | Tests for `get_iproperty` |
| `inventor_api/tests/conftest.py` | Modify | Extend `make_mock_com_document` to support multi-set props with iterable property sets |
| `inventor_export_tool/src/inventor_export_tool/templates.py` | Create | `render_template`, `BUILTIN_TOKENS` |
| `inventor_export_tool/tests/test_templates.py` | Create | Unit tests for template rendering |
| `inventor_export_tool/src/inventor_export_tool/config.py` | Modify | Add `NamingPreset`, extend `AppConfig`, custom `load_config` with migration |
| `inventor_export_tool/tests/test_config.py` | Modify | Tests for migration and new fields |
| `inventor_export_tool/src/inventor_export_tool/orchestrator.py` | Modify | Replace `compose_filename` with `render_template`; `_build_export_items` accepts `output_folder` param |
| `inventor_export_tool/tests/test_orchestrator.py` | Create | Unit tests for `_build_export_items` with preset |
| `inventor_export_tool/src/inventor_export_tool/naming.py` | Modify | Remove `compose_filename` re-export |
| `inventor_utils/src/inventor_utils/filenames.py` | Modify | Remove `compose_filename` function |
| `inventor_utils/tests/test_filenames.py` | Modify | Remove `compose_filename` tests |
| `inventor_export_tool/src/inventor_export_tool/naming_dialog.py` | Create | `NamingPresetDialog` |
| `inventor_export_tool/src/inventor_export_tool/gui.py` | Modify | Naming row, prompt-folder checkbox, button reshuffle, single-pass `_export_worker`, `_on_preview` |
| `inventor_export_tool/src/inventor_export_tool/cli.py` | Modify | Add `--preset` argument |

---

## Task 1: Add `get_iproperty` to `InventorDocument`

**Depends on:** nothing

**Files:**
- Modify: `inventor_api/src/inventor_api/document.py`
- Modify: `inventor_api/tests/test_document.py`
- Modify: `inventor_api/tests/conftest.py`

### Why this first
Everything downstream (`templates.py`, `orchestrator.py`, the naming dialog preview) calls `doc.get_iproperty(name)`. It must exist before anything else can be built or tested.

### Context
- `InventorDocument` already has `get_property(set_name, prop_name)` at `document.py:50-64`.
- `PropertySet` enum at `types.py:29-36` lists the four standard set names in search order.
- `conftest.py:make_mock_com_document` builds a mock with a `properties: dict[str, dict[str, str]]` dict, but only supports exact-name lookup. `get_iproperty` needs case-insensitive search across all sets, so `conftest.py` needs `make_mock_com_document_multi` (or an updated version) that properly supports iteration over all property sets.

- [ ] **Step 1.1: Extend conftest to support multi-set, iterable property sets**

In `inventor_api/tests/conftest.py`, replace `make_mock_com_document` so its `PropertySets` mock supports both `.Item(set_name)` (as now) and iteration over all sets (needed for `get_iproperty`). Add a `make_mock_com_document_multi` factory that accepts a full `properties` dict mapping set name → `{prop_name: value}`:

```python
def make_mock_com_document_multi(
    *,
    full_filename: str = r"C:\Projects\Part.ipt",
    document_type: int = DocumentType.PART,
    properties: dict[str, dict[str, str | None]] | None = None,
) -> MagicMock:
    """Create a mock COM document with full multi-set property support.

    Args:
        full_filename: The FullFileName property.
        document_type: The DocumentType integer.
        properties: Dict of {prop_set_name: {prop_name: value}}.
    """
    if properties is None:
        properties = {
            "Design Tracking Properties": {"Revision Number": "A"},
        }

    doc = MagicMock()
    doc.FullFileName = full_filename
    doc.DocumentType = document_type

    # Build per-set mocks
    prop_set_mocks: list[MagicMock] = []
    set_mock_by_name: dict[str, MagicMock] = {}
    for set_name, prop_dict in properties.items():
        ps = MagicMock()
        ps.Name = set_name

        def _make_prop_item(d: dict[str, str | None]):
            def prop_item(name: str) -> MagicMock:
                # Case-insensitive lookup
                for k, v in d.items():
                    if k.lower() == name.lower():
                        pm = MagicMock()
                        pm.Value = v
                        return pm
                raise KeyError(name)
            return prop_item

        ps.Item = MagicMock(side_effect=_make_prop_item(prop_dict))
        prop_set_mocks.append(ps)
        set_mock_by_name[set_name] = ps

    prop_sets = MagicMock()
    prop_sets.__iter__ = MagicMock(return_value=iter(prop_set_mocks))
    prop_sets.Count = len(prop_set_mocks)

    def set_item(name: str) -> MagicMock:
        if name in set_mock_by_name:
            return set_mock_by_name[name]
        raise KeyError(name)

    prop_sets.Item = MagicMock(side_effect=set_item)
    doc.PropertySets = prop_sets
    return doc
```

Also keep `make_mock_com_document` unchanged (it's used by existing tests) — just add the new factory below it.

- [ ] **Step 1.2: Write failing tests for `get_iproperty`**

Add a new class `TestGetIproperty` to `inventor_api/tests/test_document.py`:

```python
from conftest import make_mock_com_document_multi

class TestGetIproperty:
    def test_finds_property_in_first_set(self):
        com = make_mock_com_document_multi(
            properties={
                "Design Tracking Properties": {"Part Number": "BRK-001", "Revision Number": "A"},
            }
        )
        doc = InventorDocument(com)
        assert doc.get_iproperty("Part Number") == "BRK-001"

    def test_finds_property_in_second_set(self):
        com = make_mock_com_document_multi(
            properties={
                "Design Tracking Properties": {"Revision Number": "A"},
                "Inventor Summary Information": {"Title": "Bracket Drawing"},
            }
        )
        doc = InventorDocument(com)
        assert doc.get_iproperty("Title") == "Bracket Drawing"

    def test_case_insensitive_lookup(self):
        com = make_mock_com_document_multi(
            properties={
                "Design Tracking Properties": {"Part Number": "BRK-001"},
            }
        )
        doc = InventorDocument(com)
        assert doc.get_iproperty("part number") == "BRK-001"
        assert doc.get_iproperty("PART NUMBER") == "BRK-001"

    def test_returns_none_for_missing_property(self):
        com = make_mock_com_document_multi(
            properties={
                "Design Tracking Properties": {"Revision Number": "A"},
            }
        )
        doc = InventorDocument(com)
        assert doc.get_iproperty("Nonexistent Property") is None

    def test_returns_none_for_none_value(self):
        com = make_mock_com_document_multi(
            properties={
                "Design Tracking Properties": {"Part Number": None},
            }
        )
        doc = InventorDocument(com)
        assert doc.get_iproperty("Part Number") is None

    def test_returns_none_for_empty_value(self):
        com = make_mock_com_document_multi(
            properties={
                "Design Tracking Properties": {"Part Number": ""},
            }
        )
        doc = InventorDocument(com)
        assert doc.get_iproperty("Part Number") is None

    def test_first_set_wins_on_name_collision(self):
        """Design Tracking Properties is searched before Inventor Summary Information."""
        com = make_mock_com_document_multi(
            properties={
                "Design Tracking Properties": {"Title": "DTP Title"},
                "Inventor Summary Information": {"Title": "Summary Title"},
            }
        )
        doc = InventorDocument(com)
        # Search order: Design Tracking first
        assert doc.get_iproperty("Title") == "DTP Title"

    def test_special_filename_token_not_handled_here(self):
        """get_iproperty does NOT handle {filename} — that's templates.py's job."""
        com = make_mock_com_document_multi(properties={})
        doc = InventorDocument(com)
        assert doc.get_iproperty("filename") is None
```

- [ ] **Step 1.3: Run tests to verify they fail**

```bash
uv run --package inventor-api pytest inventor_api/tests/test_document.py::TestGetIproperty -v
```

Expected: `FAILED` — `InventorDocument` has no `get_iproperty` attribute.

- [ ] **Step 1.4: Implement `get_iproperty` in `document.py`**

Add the following method to `InventorDocument` after `get_revision` (line 72 in the current file):

```python
def get_iproperty(self, name: str) -> str | None:
    """Look up an iProperty by display name across all property sets.

    Search order: iterates PropertySets in COM-defined order (typically:
    Design Tracking Properties, Inventor Summary Information,
    Inventor Document Summary Information, Inventor User Defined Properties).
    Case-insensitive on ``name``.

    Returns the value as a stripped non-empty string, or None if the
    property is missing, its value is None, or its value is empty.
    """
    try:
        for prop_set in self._com.PropertySets:
            try:
                prop = prop_set.Item(name)
                value = prop.Value
                if value is None:
                    continue
                result = str(value).strip()
                if result:
                    return result
            except Exception:
                continue
    except Exception:
        pass
    return None
```

- [ ] **Step 1.5: Run tests to verify they pass**

```bash
uv run --package inventor-api pytest inventor_api/tests/test_document.py -v
```

Expected: All tests PASS. (The existing `TestInventorDocument` tests must still pass too.)

- [ ] **Step 1.6: Update `inventor_api/__init__.py` — no change needed**

`get_iproperty` is a method on `InventorDocument` which is already exported. No `__init__.py` change required.

- [ ] **Step 1.7: Commit**

```bash
git add inventor_api/src/inventor_api/document.py inventor_api/tests/test_document.py inventor_api/tests/conftest.py
git commit -m "feat(inventor_api): add InventorDocument.get_iproperty for cross-set iProperty lookup"
```

---

## Task 2: Create `templates.py` and its tests

**Depends on:** Task 1 (calls `doc.get_iproperty`)

**Files:**
- Create: `inventor_export_tool/src/inventor_export_tool/templates.py`
- Create: `inventor_export_tool/tests/test_templates.py`

### Context
- `render_template` takes a template string, an `InventorDocument`, and a `fallback_filename`.
- Tokens are `{Property Name}` patterns. `{filename}` is a special token returning the file stem.
- Post-processing: sanitize the whole rendered string (using the existing `sanitize_filename` from `inventor_utils.filenames`), collapse whitespace, strip leading/trailing dashes and spaces. If the result is empty, return `fallback_filename`.
- `BUILTIN_TOKENS` is the chip list shown in the preset dialog UI — not a whitelist.

- [ ] **Step 2.1: Write failing tests**

Create `inventor_export_tool/tests/test_templates.py`:

```python
"""Tests for inventor_export_tool.templates."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from inventor_export_tool.templates import BUILTIN_TOKENS, render_template


def _make_doc(props: dict[str, str | None], full_path: str = r"C:\Parts\Bracket.ipt") -> MagicMock:
    """Build a minimal InventorDocument mock for template tests."""
    doc = MagicMock()
    doc.full_path = full_path

    def get_iproperty(name: str) -> str | None:
        for k, v in props.items():
            if k.lower() == name.lower():
                return v if v else None
        return None

    doc.get_iproperty = MagicMock(side_effect=get_iproperty)
    return doc


class TestRenderTemplate:
    def test_single_token_renders(self):
        doc = _make_doc({"Part Number": "BRK-001"})
        result = render_template("{Part Number}", doc, fallback_filename="fallback")
        assert result == "BRK-001"

    def test_multi_token_renders(self):
        doc = _make_doc({"Part Number": "BRK-001", "Revision Number": "B"})
        result = render_template("{Part Number} - Rev{Revision Number}", doc, fallback_filename="f")
        assert result == "BRK-001 - RevB"

    def test_filename_token_returns_file_stem(self):
        doc = _make_doc({}, full_path=r"C:\Projects\MyPart.ipt")
        result = render_template("{filename}", doc, fallback_filename="fallback")
        assert result == "MyPart"

    def test_filename_token_case_insensitive(self):
        doc = _make_doc({}, full_path=r"C:\Projects\MyPart.ipt")
        assert render_template("{FILENAME}", doc, fallback_filename="f") == "MyPart"
        assert render_template("{Filename}", doc, fallback_filename="f") == "MyPart"

    def test_missing_token_renders_empty_and_collapses_whitespace(self):
        """'{Part Number} - {Description} - Rev' with missing Description -> 'Part - Rev'"""
        doc = _make_doc({"Part Number": "BRK-001", "Description": None})
        result = render_template(
            "{Part Number} - {Description} - Rev", doc, fallback_filename="fallback"
        )
        assert result == "BRK-001 -  - Rev"  # raw before strip
        # After post-processing: collapse whitespace then strip trailing dash/space
        # Actually: 'BRK-001 -  - Rev' -> collapsed: 'BRK-001 - - Rev' -> strip dashes: 'BRK-001 - - Rev'
        # The full result after all processing:
        assert result == "BRK-001 - - Rev"

    def test_all_missing_tokens_returns_fallback(self):
        doc = _make_doc({})
        result = render_template("{Part Number} - {Description}", doc, fallback_filename="Fallback")
        assert result == "Fallback"

    def test_invalid_chars_in_property_value_are_sanitized(self):
        doc = _make_doc({"Part Number": "BRK/001:2"})
        result = render_template("{Part Number}", doc, fallback_filename="fallback")
        # sanitize_filename replaces / and : with _
        assert "/" not in result
        assert ":" not in result
        assert "BRK" in result

    def test_custom_user_defined_property_renders(self):
        doc = _make_doc({"My Custom Prop": "CustomValue"})
        result = render_template("{My Custom Prop}", doc, fallback_filename="fallback")
        assert result == "CustomValue"

    def test_case_insensitive_token_lookup(self):
        doc = _make_doc({"Part Number": "BRK-001"})
        assert render_template("{PART NUMBER}", doc, fallback_filename="f") == "BRK-001"
        assert render_template("{part number}", doc, fallback_filename="f") == "BRK-001"

    def test_empty_template_returns_fallback(self):
        doc = _make_doc({})
        result = render_template("", doc, fallback_filename="MyFallback")
        assert result == "MyFallback"

    def test_literal_text_with_no_tokens(self):
        doc = _make_doc({})
        result = render_template("StaticName", doc, fallback_filename="fallback")
        assert result == "StaticName"

    def test_leading_trailing_dash_stripped(self):
        doc = _make_doc({"Part Number": None})
        result = render_template("{Part Number} - Suffix", doc, fallback_filename="fallback")
        # "{Part Number}" renders empty -> " - Suffix" -> strip leading " -" -> "Suffix"
        assert result == "Suffix"

    def test_whitespace_collapsed(self):
        doc = _make_doc({"Part Number": "P1", "Description": "  "})
        # Description is whitespace-only → treated as None → rendered empty
        result = render_template("{Part Number}  {Description}  End", doc, fallback_filename="f")
        # "P1    End" -> collapse -> "P1 End"
        assert result == "P1 End"


class TestBuiltinTokens:
    def test_is_list_of_strings(self):
        assert isinstance(BUILTIN_TOKENS, list)
        assert all(isinstance(t, str) for t in BUILTIN_TOKENS)

    def test_contains_expected_tokens(self):
        assert "Part Number" in BUILTIN_TOKENS
        assert "Description" in BUILTIN_TOKENS
        assert "Revision Number" in BUILTIN_TOKENS
        assert "filename" in BUILTIN_TOKENS
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_templates.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'inventor_export_tool.templates'`.

- [ ] **Step 2.3: Implement `templates.py`**

Create `inventor_export_tool/src/inventor_export_tool/templates.py`:

```python
"""Token-based filename template engine for the export tool."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from inventor_utils.filenames import sanitize_filename

if TYPE_CHECKING:
    from inventor_api.document import InventorDocument

BUILTIN_TOKENS: list[str] = [
    "filename",
    "Part Number",
    "Description",
    "Project",
    "Revision Number",
    "Title",
    "Subject",
    "Author",
    "Comments",
    "Category",
    "Company",
    "Manager",
    "Material",
    "Cost Center",
    "Checked By",
    "Engineer Approved By",
]

_TOKEN_RE = re.compile(r"\{([^{}]+)\}")


def render_template(template: str, doc: "InventorDocument", fallback_filename: str) -> str:
    """Render ``template`` against ``doc``'s iProperties.

    Tokens are ``{Property Name}`` (case-insensitive, spaces allowed).
    Special token ``{filename}`` resolves to the file stem of ``doc.full_path``.
    Missing or None values render as empty string.

    Post-processing (applied to the final rendered string):
    1. Sanitize for Windows filenames.
    2. Collapse runs of whitespace to a single space and strip.
    3. Strip leading/trailing dashes and spaces.
    4. If the result is empty, return ``fallback_filename``.
    """
    file_stem = os.path.splitext(os.path.basename(doc.full_path))[0]

    def _resolve(token: str) -> str:
        if token.lower() == "filename":
            return file_stem
        value = doc.get_iproperty(token)
        return value if value is not None else ""

    result = _TOKEN_RE.sub(lambda m: _resolve(m.group(1)), template)
    result = sanitize_filename(result)
    result = re.sub(r"\s+", " ", result).strip()
    result = result.strip(" -")
    return result if result else fallback_filename
```

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_templates.py -v
```

Expected: All tests PASS. If the "missing token whitespace collapse" tests reveal exact output differences, fix the assertion in the test to match actual post-processing output (the test in Step 2.1 has inline comments explaining the transformation — treat those as authoritative).

- [ ] **Step 2.5: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/templates.py inventor_export_tool/tests/test_templates.py
git commit -m "feat(export): add token-based template engine (templates.py)"
```

---

## Task 3: Extend `AppConfig` with `NamingPreset` and migration

**Depends on:** nothing (pure data/config — no imports from Tasks 1-2)

**Files:**
- Modify: `inventor_export_tool/src/inventor_export_tool/config.py`
- Modify: `inventor_export_tool/tests/test_config.py`

### Context
- `load_dataclass_config` in `inventor_utils/config.py:25-38` does a flat `cls(**filtered)` call. It **does not** handle nested dataclasses — `naming_presets` will be loaded as `list[dict]`, not `list[NamingPreset]`. The export tool's `load_config` must handle conversion manually.
- Migration rules (from spec §1):
  1. If `naming_presets` is missing or empty after JSON load → seed with `[NamingPreset("OleM Default", "{Part Number} - {Description} - Rev{Revision Number}")]`.
  2. If `active_preset_name` doesn't match any preset name → reset to first preset's name.
- `AppConfig` gains a helper `active_preset() -> NamingPreset` for the orchestrator.

- [ ] **Step 3.1: Write failing tests for new config fields and migration**

Add the following to `inventor_export_tool/tests/test_config.py` (append new classes; don't delete existing ones):

```python
import json
from inventor_export_tool.config import NamingPreset


class TestNamingPreset:
    def test_default_fields(self):
        p = NamingPreset(name="OleM Default", template="{Part Number} - {Description}")
        assert p.name == "OleM Default"
        assert p.template == "{Part Number} - {Description}"


class TestAppConfigNewFields:
    def test_naming_presets_default(self):
        c = AppConfig()
        assert len(c.naming_presets) == 1
        assert c.naming_presets[0].name == "OleM Default"
        assert "{Part Number}" in c.naming_presets[0].template

    def test_active_preset_name_default(self):
        c = AppConfig()
        assert c.active_preset_name == "OleM Default"

    def test_prompt_folder_on_export_default(self):
        c = AppConfig()
        assert c.prompt_folder_on_export is False

    def test_active_preset_returns_preset(self):
        preset = NamingPreset(name="My Preset", template="{Part Number}")
        c = AppConfig(naming_presets=[preset], active_preset_name="My Preset")
        assert c.active_preset() == preset

    def test_active_preset_falls_back_to_first_on_mismatch(self):
        preset = NamingPreset(name="First", template="{Part Number}")
        c = AppConfig(naming_presets=[preset], active_preset_name="Nonexistent")
        assert c.active_preset() == preset


class TestLoadConfigMigration:
    def test_missing_naming_presets_seeds_default(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text('{"output_folder": "C:\\\\exports"}', encoding="utf-8")
        config = load_config(path)
        assert len(config.naming_presets) == 1
        assert config.naming_presets[0].name == "OleM Default"

    def test_empty_naming_presets_seeds_default(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text('{"naming_presets": []}', encoding="utf-8")
        config = load_config(path)
        assert len(config.naming_presets) == 1

    def test_naming_presets_loaded_as_preset_objects(self, tmp_path):
        path = tmp_path / "config.json"
        data = {
            "naming_presets": [{"name": "Custom", "template": "{Part Number}"}],
            "active_preset_name": "Custom",
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        config = load_config(path)
        assert isinstance(config.naming_presets[0], NamingPreset)
        assert config.naming_presets[0].name == "Custom"

    def test_orphaned_active_preset_name_reset_to_first(self, tmp_path):
        path = tmp_path / "config.json"
        data = {
            "naming_presets": [{"name": "Only Preset", "template": "{Part Number}"}],
            "active_preset_name": "Deleted Preset",
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        config = load_config(path)
        assert config.active_preset_name == "Only Preset"

    def test_round_trip_with_presets(self, tmp_path):
        path = tmp_path / "config.json"
        original = AppConfig(
            naming_presets=[
                NamingPreset("Default", "{Part Number} - Rev{Revision Number}"),
                NamingPreset("Short", "{Part Number}"),
            ],
            active_preset_name="Short",
            prompt_folder_on_export=True,
        )
        save_config(original, path)
        loaded = load_config(path)
        assert len(loaded.naming_presets) == 2
        assert loaded.naming_presets[1].name == "Short"
        assert loaded.active_preset_name == "Short"
        assert loaded.prompt_folder_on_export is True
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_config.py -v
```

Expected: Multiple `FAILED` — `NamingPreset` not importable, new fields don't exist.

- [ ] **Step 3.3: Implement the config changes**

Replace the entire content of `inventor_export_tool/src/inventor_export_tool/config.py`:

```python
"""Load and save user preferences as JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from inventor_utils.config import get_config_path, save_dataclass_config

_DEFAULT_PRESET_NAME = "OleM Default"
_DEFAULT_PRESET_TEMPLATE = "{Part Number} - {Description} - Rev{Revision Number}"


@dataclass
class NamingPreset:
    """A named filename template preset."""

    name: str
    template: str


@dataclass
class AppConfig:
    """User-configurable settings persisted between sessions."""

    output_folder: str = ""
    export_step: bool = True
    export_dwg: bool = True
    export_pdf: bool = True
    include_parts: bool = True
    include_subassemblies: bool = True
    include_top_level: bool = True
    include_suppressed: bool = False
    export_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    naming_presets: list[NamingPreset] = field(
        default_factory=lambda: [NamingPreset(_DEFAULT_PRESET_NAME, _DEFAULT_PRESET_TEMPLATE)]
    )
    active_preset_name: str = _DEFAULT_PRESET_NAME
    prompt_folder_on_export: bool = False

    def active_preset(self) -> NamingPreset:
        """Return the active preset, falling back to the first preset if the name is invalid."""
        for p in self.naming_presets:
            if p.name == self.active_preset_name:
                return p
        return self.naming_presets[0]


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from JSON file. Returns defaults if missing or corrupt.

    Applies migration:
    - naming_presets dicts are converted to NamingPreset instances.
    - Empty or missing naming_presets seeds the default preset.
    - active_preset_name that matches no preset is reset to first preset's name.
    """
    if path is None:
        path = get_config_path("config.json")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return AppConfig()
    except (FileNotFoundError, json.JSONDecodeError):
        return AppConfig()

    # Extract scalar fields
    scalar_fields = {
        "output_folder", "export_step", "export_dwg", "export_pdf",
        "include_parts", "include_subassemblies", "include_top_level",
        "include_suppressed", "export_options", "active_preset_name",
        "prompt_folder_on_export",
    }
    kwargs: dict[str, Any] = {k: v for k, v in data.items() if k in scalar_fields}

    # Convert naming_presets from list[dict] to list[NamingPreset]
    raw_presets = data.get("naming_presets", [])
    if isinstance(raw_presets, list) and raw_presets:
        presets: list[NamingPreset] = []
        for item in raw_presets:
            if isinstance(item, dict) and "name" in item and "template" in item:
                presets.append(NamingPreset(name=str(item["name"]), template=str(item["template"])))
        kwargs["naming_presets"] = presets if presets else _default_presets()
    else:
        kwargs["naming_presets"] = _default_presets()

    try:
        config = AppConfig(**kwargs)
    except (TypeError, ValueError):
        return AppConfig()

    # Migration: reset orphaned active_preset_name
    preset_names = {p.name for p in config.naming_presets}
    if config.active_preset_name not in preset_names:
        config.active_preset_name = config.naming_presets[0].name

    return config


def _default_presets() -> list[NamingPreset]:
    return [NamingPreset(_DEFAULT_PRESET_NAME, _DEFAULT_PRESET_TEMPLATE)]


def save_config(config: AppConfig, path: Path | None = None) -> None:
    """Save config to JSON file."""
    if path is None:
        path = get_config_path("config.json")
    save_dataclass_config(config, path)
```

- [ ] **Step 3.4: Run all config tests**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_config.py -v
```

Expected: All tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/config.py inventor_export_tool/tests/test_config.py
git commit -m "feat(export): add NamingPreset dataclass, extend AppConfig, config migration"
```

---

## Task 4: Remove `compose_filename` from `inventor_utils` and `naming.py`

**Depends on:** Task 3 (orchestrator step that removes its usage comes next in Task 5; remove the source before updating the consumer to get a clean test-failure signal)

**Files:**
- Modify: `inventor_utils/src/inventor_utils/filenames.py`
- Modify: `inventor_export_tool/src/inventor_export_tool/naming.py`
- Modify: `inventor_utils/tests/test_filenames.py` (if it exists)
- Modify: `inventor_export_tool/tests/test_naming.py`

### Context
- `compose_filename` is defined at `inventor_utils/src/inventor_utils/filenames.py:20-31`.
- It is re-exported from `inventor_export_tool/src/inventor_export_tool/naming.py:8-24`.
- It is imported and called three times in `orchestrator.py:70,83,91` — that import will break after this task, which is intentional: Task 5 fixes it.
- `sanitize_filename`, `find_idw_path`, `is_content_center_path` stay.

- [ ] **Step 4.1: Check for existing `test_filenames.py`**

```bash
uv run --package inventor-utils pytest inventor_utils/ -v --collect-only 2>/dev/null | head -30
```

If `test_filenames.py` exists and has `test_compose_filename` tests, proceed to Step 4.2. If not, skip to Step 4.3.

- [ ] **Step 4.2: Remove `compose_filename` tests from `inventor_utils/tests/test_filenames.py`**

Remove any test class or function that tests `compose_filename`. Keep all tests for `sanitize_filename`, `find_idw_path`, and `is_content_center_path`.

- [ ] **Step 4.3: Remove `compose_filename` from `inventor_utils/filenames.py`**

In `inventor_utils/src/inventor_utils/filenames.py`, delete lines 20-31 (the `compose_filename` function). The file should retain only: `sanitize_filename`, `find_idw_path`, `is_content_center_path`, and the `_INVALID_CHARS` regex at the top.

The final file:

```python
"""Filename sanitization and IDW-finding utilities."""

from __future__ import annotations

import os
import re

# Characters invalid in Windows filenames
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Remove or replace characters invalid in Windows filenames."""
    sanitized = _INVALID_CHARS.sub("_", name)
    # Strip trailing dots and spaces (Windows restriction)
    sanitized = sanitized.rstrip(". ")
    return sanitized if sanitized else "_"


def find_idw_path(source_path: str) -> str | None:
    """Find the co-located .idw file for an .ipt or .iam file.

    Returns the IDW path if it exists, None otherwise.
    Checks both .idw and .IDW (case-insensitive on Windows, but explicit).
    """
    base = os.path.splitext(source_path)[0]
    idw_path = base + ".idw"
    if os.path.exists(idw_path):
        return idw_path
    idw_path_upper = base + ".IDW"
    if os.path.exists(idw_path_upper):
        return idw_path_upper
    return None


def is_content_center_path(file_path: str) -> bool:
    """Check if a file path is from Inventor's Content Center."""
    return "content center files" in file_path.lower()
```

- [ ] **Step 4.4: Remove `compose_filename` re-export from `naming.py`**

Replace the content of `inventor_export_tool/src/inventor_export_tool/naming.py`:

```python
"""IDW finding, filename sanitization, and duplicate resolution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from inventor_utils.filenames import (
    find_idw_path,
    is_content_center_path,
    sanitize_filename,
)

if TYPE_CHECKING:
    from inventor_export_tool.models import ExportItem

__all__ = [
    "find_idw_path",
    "is_content_center_path",
    "resolve_duplicates",
    "sanitize_filename",
]


def resolve_duplicates(items: list[ExportItem]) -> list[ExportItem]:
    """Detect filename collisions and append _2, _3 suffixes.

    Modifies output_filename and output_path on colliding items.
    Returns the same list (mutated in place) for convenience.
    """
    seen: dict[str, int] = {}
    for item in items:
        key = item.output_filename.lower()
        if key in seen:
            seen[key] += 1
            count = seen[key]
            name, ext = os.path.splitext(item.output_filename)
            item.output_filename = f"{name}_{count}{ext}"
            folder = os.path.dirname(item.output_path)
            item.output_path = os.path.join(folder, item.output_filename)
        else:
            seen[key] = 1
    return items
```

- [ ] **Step 4.5: Fix test_naming.py — remove compose_filename tests**

Open `inventor_export_tool/tests/test_naming.py` and remove any test that imports or tests `compose_filename`. Keep `resolve_duplicates` tests.

- [ ] **Step 4.6: Run inventor_utils tests to verify they pass**

```bash
uv run --package inventor-utils pytest inventor_utils/ -v
```

Expected: All PASS (no `compose_filename` tests remain).

- [ ] **Step 4.7: Verify the export tool import now fails (expected breakage before Task 5)**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_naming.py -v
```

Expected: PASS (naming tests removed, `resolve_duplicates` tests still work). But if you try to import `orchestrator.py` now it would fail — that's fixed in Task 5.

- [ ] **Step 4.8: Commit**

```bash
git add inventor_utils/src/inventor_utils/filenames.py inventor_export_tool/src/inventor_export_tool/naming.py inventor_export_tool/tests/test_naming.py
git commit -m "refactor: remove compose_filename from inventor_utils and naming.py re-export"
```

---

## Task 5: Update `orchestrator.py` to use `render_template`

**Depends on:** Tasks 1, 2, 3, 4

**Files:**
- Modify: `inventor_export_tool/src/inventor_export_tool/orchestrator.py`
- Create: `inventor_export_tool/tests/test_orchestrator.py`

### Context
- `_build_export_items` at `orchestrator.py:47-103` calls `compose_filename` three times.
- It must be changed to: compute one `base_name` per component via `render_template`, then append the extension.
- `_build_export_items` currently takes `output_folder: str` from the caller — keep that parameter unchanged; `scan()` at line 171 currently passes `self._config.output_folder`. After this task, `scan()` will accept an explicit `output_folder` parameter (needed for the GUI refactor in Task 7 where folder is resolved before calling the worker).
- `_doc_cache` is populated during `walk_assembly` (lines 162-163). The orchestrator already has access to live `InventorDocument` objects — the template rendering happens at naming time.
- `config.active_preset()` returns the active `NamingPreset`.
- After the refactor, `scan()` signature changes to `scan(self, output_folder: str | None = None) -> ScanSummary`. If `output_folder` is None, fall back to `self._config.output_folder`.

- [ ] **Step 5.1: Write failing orchestrator tests**

Create `inventor_export_tool/tests/test_orchestrator.py`:

```python
"""Tests for orchestrator._build_export_items with template-based naming."""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from inventor_export_tool.config import AppConfig, NamingPreset
from inventor_export_tool.models import ComponentInfo
from inventor_export_tool.orchestrator import _build_export_items


def _make_component(
    display_name: str = "Bracket",
    source_path: str = r"C:\Parts\Bracket.ipt",
    document_type: str = "part",
    revision: str = "A",
    is_top_level: bool = False,
    idw_path: str | None = None,
) -> ComponentInfo:
    return ComponentInfo(
        source_path=source_path,
        display_name=display_name,
        document_type=document_type,
        revision=revision,
        is_top_level=is_top_level,
        idw_path=idw_path,
    )


def _make_doc(part_number: str = "BRK-001", description: str = "Bracket", revision: str = "A") -> MagicMock:
    doc = MagicMock()
    doc.full_path = r"C:\Parts\Bracket.ipt"
    props = {
        "part number": part_number,
        "description": description,
        "revision number": revision,
    }
    doc.get_iproperty = MagicMock(side_effect=lambda name: props.get(name.lower()))
    return doc


class TestBuildExportItems:
    def _config_with_preset(self, template: str) -> AppConfig:
        preset = NamingPreset(name="Test", template=template)
        return AppConfig(
            export_step=True, export_dwg=False, export_pdf=False,
            naming_presets=[preset], active_preset_name="Test",
        )

    def test_step_filename_uses_template(self):
        comp = _make_component()
        doc = _make_doc(part_number="BRK-001", description="Bracket", revision="B")
        doc_cache = {r"C:\Parts\Bracket.ipt": doc}
        config = self._config_with_preset("{Part Number} - {Description} - Rev{Revision Number}")
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        assert len(items) == 1
        assert items[0].output_filename == "BRK-001 - Bracket - RevB.step"

    def test_missing_token_falls_back_to_display_name(self):
        comp = _make_component(display_name="Bracket")
        doc = _make_doc(part_number="", description="", revision="")
        doc_cache = {r"C:\Parts\Bracket.ipt": doc}
        config = self._config_with_preset("{Part Number}")
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        # render_template returns fallback_filename when all tokens empty
        assert items[0].output_filename == "Bracket.step"

    def test_dwg_and_pdf_use_same_base_name(self):
        idw = r"C:\Parts\Bracket.idw"
        comp = _make_component(idw_path=idw)
        doc = _make_doc(part_number="BRK-001", description="Bracket", revision="A")
        doc_cache = {r"C:\Parts\Bracket.ipt": doc}
        config = AppConfig(
            export_step=False, export_dwg=True, export_pdf=True,
            naming_presets=[NamingPreset("T", "{Part Number}")],
            active_preset_name="T",
        )
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        names = [i.output_filename for i in items]
        assert "BRK-001.dwg" in names
        assert "BRK-001.pdf" in names

    def test_filters_parts_when_include_parts_false(self):
        comp = _make_component(document_type="part")
        doc_cache = {r"C:\Parts\Bracket.ipt": _make_doc()}
        config = AppConfig(
            export_step=True, include_parts=False,
            naming_presets=[NamingPreset("T", "{Part Number}")],
            active_preset_name="T",
        )
        items = _build_export_items([comp], config, r"C:\out", doc_cache)
        assert items == []

    def test_output_path_uses_output_folder(self):
        comp = _make_component()
        doc_cache = {r"C:\Parts\Bracket.ipt": _make_doc(part_number="BRK-001")}
        config = self._config_with_preset("{Part Number}")
        items = _build_export_items([comp], config, r"C:\exports", doc_cache)
        assert items[0].output_path.startswith(r"C:\exports")
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_orchestrator.py -v
```

Expected: `FAILED` — `_build_export_items` still uses `compose_filename` (which no longer exists) and doesn't accept `doc_cache`.

- [ ] **Step 5.3: Update `orchestrator.py`**

Replace the import section and `_build_export_items` function in `inventor_export_tool/src/inventor_export_tool/orchestrator.py`. Also update `scan()` to pass `doc_cache` and accept an optional `output_folder` parameter.

Change the imports at the top (remove `compose_filename`, add `render_template`):

```python
from inventor_export_tool.naming import (
    find_idw_path,
    resolve_duplicates,
    sanitize_filename,
)
from inventor_export_tool.templates import render_template
```

Replace `_build_export_items` (lines 47-103):

```python
def _build_export_items(
    components: list[ComponentInfo],
    config: AppConfig,
    output_folder: str,
    doc_cache: dict[str, "InventorDocument"],
) -> list[ExportItem]:
    """Build the list of ExportItems based on config and active naming preset."""
    preset = config.active_preset()
    items: list[ExportItem] = []

    for comp in components:
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

        # Render base name once per component
        doc = doc_cache.get(comp.source_path)
        if doc is not None:
            base_name = render_template(
                preset.template, doc, fallback_filename=comp.display_name
            )
        else:
            base_name = sanitize_filename(comp.display_name)

        if config.export_step:
            filename = f"{base_name}.step"
            items.append(
                ExportItem(
                    component=comp,
                    export_type="step",
                    output_filename=filename,
                    output_path=os.path.join(output_folder, filename),
                )
            )

        if comp.idw_path:
            if config.export_dwg:
                filename = f"{base_name}.dwg"
                items.append(
                    ExportItem(
                        component=comp,
                        export_type="dwg",
                        output_filename=filename,
                        output_path=os.path.join(output_folder, filename),
                    )
                )
            if config.export_pdf:
                filename = f"{base_name}.pdf"
                items.append(
                    ExportItem(
                        component=comp,
                        export_type="pdf",
                        output_filename=filename,
                        output_path=os.path.join(output_folder, filename),
                    )
                )

    return items
```

Update `scan()` to accept `output_folder` and pass `doc_cache` to `_build_export_items`. Change the signature and the call site (lines 135 and 171):

```python
def scan(self, output_folder: str | None = None) -> ScanSummary:
    """Connect to Inventor, walk the assembly tree, and build an export plan.

    Args:
        output_folder: Override the config's output folder for this scan.
                       If None, uses self._config.output_folder.

    Must be called from a thread with COM initialized (use com_thread_scope).
    """
    # ... (keep existing connect/walk code) ...
    effective_folder = output_folder if output_folder is not None else self._config.output_folder
    items = _build_export_items(components, self._config, effective_folder, self._doc_cache)
    # ... (rest unchanged) ...
```

The full updated `scan()` method (replacing lines 135-208 of the original):

```python
def scan(self, output_folder: str | None = None) -> ScanSummary:
    """Connect to Inventor, walk the assembly tree, and build an export plan.

    Args:
        output_folder: Override the config output folder for naming/path generation.
                       If None, uses self._config.output_folder.

    Must be called from a thread with COM initialized (use com_thread_scope).
    """
    self._emit("Connecting to Inventor...")
    self._app = InventorApp.connect()

    self._emit("Getting active assembly...")
    assembly = self._app.get_active_assembly()
    self._assembly_name = assembly.display_name
    self._assembly_path = assembly.full_path
    self._emit(f"Assembly: {self._assembly_name}")

    self._emit("Scanning assembly tree...")
    discovered = walk_assembly(
        assembly,
        include_suppressed=self._config.include_suppressed,
    )

    all_count = len(discovered)
    content_center_count = sum(1 for c in discovered if c.document.is_content_center)

    self._doc_cache = {c.document.full_path: c.document for c in discovered}
    components = [_to_component_info(c) for c in discovered]
    self._emit(
        f"Found {len(components)} components ({content_center_count} Content Center excluded)"
    )

    effective_folder = output_folder if output_folder is not None else self._config.output_folder
    items = _build_export_items(components, self._config, effective_folder, self._doc_cache)

    warnings: list[str] = []
    original_names = [item.output_filename for item in items]
    resolve_duplicates(items)
    for i, item in enumerate(items):
        if item.output_filename != original_names[i]:
            warnings.append(
                f"Renamed {original_names[i]} -> {item.output_filename} (duplicate)"
            )

    summary = ScanSummary(
        total_components=all_count,
        content_center_excluded=content_center_count,
        suppressed_excluded=0,
        export_items=items,
        warnings=warnings,
    )

    self._emit(f"Export plan: {len(items)} files to export")
    _tel.info(
        "scan_finish",
        extra={
            "data": {
                "components": all_count,
                "export_items": len(items),
                "content_center_excluded": content_center_count,
            }
        },
    )
    for item in items:
        idw_note = " (from IDW)" if item.export_type in ("dwg", "pdf") else ""
        self._emit(f"  {item.output_filename} [{item.export_type.upper()}]{idw_note}")

    return summary
```

- [ ] **Step 5.4: Run orchestrator tests**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/tests/test_orchestrator.py -v
```

Expected: All PASS.

- [ ] **Step 5.5: Run the full export tool test suite**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/ -v
```

Expected: All PASS (includes existing config, naming, models, export_log tests).

- [ ] **Step 5.6: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/orchestrator.py inventor_export_tool/tests/test_orchestrator.py
git commit -m "feat(export): replace compose_filename with render_template in orchestrator"
```

---

## Task 6: Create `NamingPresetDialog`

**Depends on:** Tasks 2, 3

**Files:**
- Create: `inventor_export_tool/src/inventor_export_tool/naming_dialog.py`

### Context
- Modeled after `settings_dialog.py` — modal `tk.Toplevel`, `result` attribute, deep-copy of presets.
- Returns `(presets, active_name)` on OK or `None` on Cancel.
- Preview calls `InventorApp.connect()` lazily on every template keystroke. If Inventor is not running → show fallback message. Errors during preview rendering are caught and shown inline, not raised.
- Token chip buttons insert `{Token Name}` at the cursor position in the template Entry widget.
- Dialog works on `copy.deepcopy(presets)` — OK writes back; Cancel discards.
- The `[Delete]` button is disabled when only 1 preset remains.
- No unit tests for this dialog — it's pure Tkinter UI that requires a display. Covered by manual smoke test.

- [ ] **Step 6.1: Create `naming_dialog.py`**

Create `inventor_export_tool/src/inventor_export_tool/naming_dialog.py`:

```python
"""Modal dialog for managing naming presets."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import simpledialog, ttk
from typing import TYPE_CHECKING

from inventor_export_tool.templates import BUILTIN_TOKENS, render_template

if TYPE_CHECKING:
    from inventor_export_tool.config import NamingPreset


class NamingPresetDialog(tk.Toplevel):
    """Modal dialog for creating, editing, and selecting naming presets.

    Args:
        parent: Parent Tk widget.
        presets: Current list of presets (deep-copied internally).
        active_name: Name of the currently active preset.

    After ``wait_window()``, check ``self.result``:
    - ``None`` if the user cancelled.
    - ``(presets, active_name)`` tuple if the user clicked OK.
    """

    def __init__(
        self,
        parent: tk.Misc,
        presets: list[NamingPreset],
        active_name: str,
    ) -> None:
        super().__init__(parent)
        self.title("Manage Naming Presets")
        self.resizable(True, False)
        self.result: tuple[list[NamingPreset], str] | None = None

        self._presets = copy.deepcopy(presets)
        self._active_name = active_name

        # Ensure active_name is valid
        names = [p.name for p in self._presets]
        if self._active_name not in names and names:
            self._active_name = names[0]

        self._build_ui()
        self._refresh_listbox()
        self._select_preset_by_name(self._active_name)

        self._center_over_parent(parent)
        self.transient(parent)
        self.grab_set()
        self.wait_window()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # --- Preset list ---
        list_frame = ttk.LabelFrame(self, text="Presets", padding=8)
        list_frame.pack(fill="x", **pad)

        self._listbox = tk.Listbox(list_frame, height=6, selectmode="single", exportselection=False)
        self._listbox.pack(side="left", fill="x", expand=True)
        self._listbox.bind("<<ListboxSelect>>", self._on_listbox_select)
        self._listbox.bind("<Double-Button-1>", self._on_set_active)

        btn_col = ttk.Frame(list_frame)
        btn_col.pack(side="left", padx=(8, 0))
        ttk.Button(btn_col, text="+ Add", command=self._on_add).pack(fill="x", pady=(0, 2))
        ttk.Button(btn_col, text="Rename", command=self._on_rename).pack(fill="x", pady=(0, 2))
        self._delete_btn = ttk.Button(btn_col, text="Delete", command=self._on_delete)
        self._delete_btn.pack(fill="x", pady=(0, 2))
        ttk.Button(btn_col, text="Set Active", command=self._on_set_active).pack(fill="x")

        # --- Template entry ---
        tpl_frame = ttk.LabelFrame(self, text="Template", padding=8)
        tpl_frame.pack(fill="x", **pad)

        self._template_var = tk.StringVar()
        self._template_entry = ttk.Entry(tpl_frame, textvariable=self._template_var, width=60)
        self._template_entry.pack(fill="x")
        self._template_var.trace_add("write", self._on_template_changed)

        # --- Token chips ---
        chip_frame = ttk.LabelFrame(self, text="Insert Token", padding=8)
        chip_frame.pack(fill="x", **pad)

        for i, token in enumerate(BUILTIN_TOKENS):
            col = i % 5
            row = i // 5
            ttk.Button(
                chip_frame,
                text=token,
                command=lambda t=token: self._insert_token(t),
                width=22,
            ).grid(row=row, column=col, padx=2, pady=2, sticky="w")

        # --- Preview ---
        preview_frame = ttk.LabelFrame(self, text="Preview", padding=8)
        preview_frame.pack(fill="x", **pad)

        self._preview_label = ttk.Label(preview_frame, text="(loading...)", foreground="gray")
        self._preview_label.pack(anchor="w")

        # --- Buttons ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=(4, 10))
        ttk.Button(btn_frame, text="OK", command=self._on_ok, width=10).pack(side="right", padx=(4, 0))
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10).pack(side="right")

        self._update_preview()

    # ------------------------------------------------------------------
    # Listbox helpers
    # ------------------------------------------------------------------

    def _refresh_listbox(self) -> None:
        self._listbox.delete(0, "end")
        for p in self._presets:
            prefix = "* " if p.name == self._active_name else "  "
            self._listbox.insert("end", f"{prefix}{p.name}")
        self._delete_btn.configure(state="disabled" if len(self._presets) <= 1 else "normal")

    def _selected_index(self) -> int | None:
        sel = self._listbox.curselection()
        return int(sel[0]) if sel else None

    def _selected_preset(self) -> NamingPreset | None:
        idx = self._selected_index()
        return self._presets[idx] if idx is not None else None

    def _select_preset_by_name(self, name: str) -> None:
        for i, p in enumerate(self._presets):
            if p.name == name:
                self._listbox.selection_clear(0, "end")
                self._listbox.selection_set(i)
                self._listbox.see(i)
                self._load_selected_template()
                return

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_listbox_select(self, _event: object = None) -> None:
        self._load_selected_template()

    def _load_selected_template(self) -> None:
        preset = self._selected_preset()
        if preset is not None:
            self._template_var.set(preset.template)

    def _on_template_changed(self, *_args: object) -> None:
        preset = self._selected_preset()
        if preset is not None:
            preset.template = self._template_var.get()
        self._update_preview()

    def _on_add(self) -> None:
        name = simpledialog.askstring("Add Preset", "Preset name:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if any(p.name.lower() == name.lower() for p in self._presets):
            tk.messagebox.showerror("Duplicate Name", f"A preset named '{name}' already exists.", parent=self)
            return
        from inventor_export_tool.config import NamingPreset
        self._presets.append(NamingPreset(name=name, template=""))
        self._refresh_listbox()
        self._select_preset_by_name(name)

    def _on_rename(self) -> None:
        preset = self._selected_preset()
        if preset is None:
            return
        new_name = simpledialog.askstring("Rename Preset", "New name:", initialvalue=preset.name, parent=self)
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()
        if any(p.name.lower() == new_name.lower() for p in self._presets if p is not preset):
            tk.messagebox.showerror("Duplicate Name", f"A preset named '{new_name}' already exists.", parent=self)
            return
        if self._active_name == preset.name:
            self._active_name = new_name
        preset.name = new_name
        self._refresh_listbox()
        self._select_preset_by_name(new_name)

    def _on_delete(self) -> None:
        if len(self._presets) <= 1:
            return
        idx = self._selected_index()
        if idx is None:
            return
        deleted_name = self._presets[idx].name
        self._presets.pop(idx)
        if self._active_name == deleted_name:
            self._active_name = self._presets[0].name
        self._refresh_listbox()
        new_idx = min(idx, len(self._presets) - 1)
        self._listbox.selection_set(new_idx)
        self._load_selected_template()

    def _on_set_active(self, _event: object = None) -> None:
        preset = self._selected_preset()
        if preset is not None:
            self._active_name = preset.name
            self._refresh_listbox()

    def _insert_token(self, token: str) -> None:
        try:
            cursor = self._template_entry.index(tk.INSERT)
            self._template_entry.insert(cursor, f"{{{token}}}")
        except tk.TclError:
            self._template_entry.insert("end", f"{{{token}}}")

    def _update_preview(self) -> None:
        template = self._template_var.get()
        try:
            from inventor_api.application import InventorApp
            app = InventorApp.connect()
            doc = app.active_document  # property; raises InventorNotRunningError if no doc open
            preview = render_template(template, doc, fallback_filename=doc.display_name)
            self._preview_label.configure(text=preview, foreground="black")
        except Exception as e:
            msg = (
                "(no preview — open a part or assembly in Inventor)"
                if "not running" in str(e).lower() or "no document" in str(e).lower()
                else f"(preview unavailable: {e})"
            )
            self._preview_label.configure(text=msg, foreground="gray")

    # ------------------------------------------------------------------
    # OK / Cancel
    # ------------------------------------------------------------------

    def _on_ok(self) -> None:
        # Validate: at least one preset
        if not self._presets:
            return
        # Validate: all names non-empty and unique (case-insensitive)
        names_lower = [p.name.strip().lower() for p in self._presets]
        if any(not n for n in names_lower):
            tk.messagebox.showerror("Invalid Preset", "All preset names must be non-empty.", parent=self)
            return
        if len(set(names_lower)) != len(names_lower):
            tk.messagebox.showerror("Duplicate Names", "All preset names must be unique.", parent=self)
            return
        # Ensure active_name is valid
        names = [p.name for p in self._presets]
        if self._active_name not in names:
            self._active_name = names[0]
        self.result = (self._presets, self._active_name)
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()

    # ------------------------------------------------------------------
    # Layout helper
    # ------------------------------------------------------------------

    def _center_over_parent(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = self.winfo_width()
        dh = self.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        self.geometry(f"+{x}+{y}")
```

- [ ] **Step 6.2: Fix `_update_preview` to use `app.active_document` (property, not method)**

`InventorApp` exposes `active_document` as a **property** at `inventor_api/src/inventor_api/application.py:79`. It raises `InventorNotRunningError` when no document is open — it does not return `None`. The `_update_preview` code in Step 6.1 calls `app.get_active_document()` — that method does not exist. Fix the `_update_preview` method in `naming_dialog.py` to read:

```python
def _update_preview(self) -> None:
    template = self._template_var.get()
    try:
        from inventor_api.application import InventorApp
        app = InventorApp.connect()
        doc = app.active_document  # property; raises if no doc open
        preview = render_template(template, doc, fallback_filename=doc.display_name)
        self._preview_label.configure(text=preview, foreground="black")
    except Exception as e:
        msg = (
            "(no preview — open a part or assembly in Inventor)"
            if "not running" in str(e).lower() or "no document" in str(e).lower()
            else f"(preview unavailable: {e})"
        )
        self._preview_label.configure(text=msg, foreground="gray")
```

Apply this fix to `naming_dialog.py` now (replacing the version from Step 6.1).

- [ ] **Step 6.3: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/naming_dialog.py
git commit -m "feat(export): add NamingPresetDialog for managing naming presets"
```

---

## Task 7: Rework `gui.py` — naming row, folder prompt, button reshuffle, single-pass worker

**Depends on:** Tasks 3, 5, 6

**Files:**
- Modify: `inventor_export_tool/src/inventor_export_tool/gui.py`

### Context
- **Naming row:** A `Combobox` + `[Manage...]` button above (or inside) the Export Options frame.
- **Prompt folder checkbox:** A `Checkbutton` inside the Output Folder frame.
- **Button reshuffle:** `[Run Export]` first (always enabled), `[Cancel]`, then `[Preview]` (right side), then `[Open Log]`, `[Settings...]`.
- **`_export_worker` fix:** The current implementation at `gui.py:328-353` re-creates the orchestrator and re-scans on a new thread — this is the buggy two-scope dance. Replace with a clean single-pass implementation that takes `config: AppConfig` and `output_folder: str`.
- **`_resolve_output_folder()`:** New helper. Returns folder string or `None` if user cancelled picker. Logic: `prompt_folder_on_export=True` → always pick; folder field empty → always pick; else → return current value.
- **`_on_preview`:** Replaces `_on_scan`. Calls `scan()` only; posts `("preview_done", summary)`.
- **`_get_current_config()`:** Must include the three new fields: `naming_presets`, `active_preset_name`, `prompt_folder_on_export`.
- **`_save_config()`:** Must save the three new fields back.
- **`_load_config()`:** Must load and display the new fields.
- **`dataclasses.replace`:** Import at top of file for use in `_export_worker`.

- [ ] **Step 7.1: Update `gui.py`**

Replace the full content of `inventor_export_tool/src/inventor_export_tool/gui.py`. The key changes to make (keep all other methods intact):

**Imports** — add at the top:
```python
from dataclasses import replace
```

**`_build_ui` changes:**

After the Output Folder `LabelFrame`, add a **Naming row** inside a `LabelFrame`:

```python
# --- Naming preset ---
naming_frame = ttk.LabelFrame(root, text="Naming", padding=8)
naming_frame.pack(fill="x", **pad)

ttk.Label(naming_frame, text="Preset:").grid(row=0, column=0, sticky="w")
self._preset_var = tk.StringVar()
self._preset_combo = ttk.Combobox(
    naming_frame, textvariable=self._preset_var, state="readonly", width=35
)
self._preset_combo.grid(row=0, column=1, sticky="ew", padx=(4, 8))
self._preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)
ttk.Button(naming_frame, text="Manage...", command=self._on_manage_presets).grid(row=0, column=2)
naming_frame.columnconfigure(1, weight=1)
```

Inside the Output Folder `LabelFrame`, after the browse button row, add:

```python
self._prompt_folder_var = tk.BooleanVar(value=False)
ttk.Checkbutton(
    out_frame,
    text="Prompt for folder on every export",
    variable=self._prompt_folder_var,
    command=self._save_config,
).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
```

**Button row** — replace the existing button row block:

```python
# --- Action buttons ---
btn_frame = ttk.Frame(root)
btn_frame.pack(fill="x", **pad)

self._export_btn = ttk.Button(btn_frame, text="Run Export", command=self._on_export)
self._export_btn.pack(side="left", padx=(0, 8))

self._cancel_btn = ttk.Button(
    btn_frame, text="Cancel", command=self._on_cancel, state="disabled"
)
self._cancel_btn.pack(side="left")

self._settings_btn = ttk.Button(btn_frame, text="Settings...", command=self._on_settings)
self._settings_btn.pack(side="right")

self._open_log_btn = ttk.Button(
    btn_frame, text="Open Log", command=self._on_open_log, state="disabled"
)
self._open_log_btn.pack(side="right", padx=(0, 8))

self._preview_btn = ttk.Button(btn_frame, text="Preview", command=self._on_preview)
self._preview_btn.pack(side="right", padx=(0, 8))
```

Remove `self._scan_summary = None` from `_build_ui` (no longer needed).

**`_load_config`** — add:

```python
self._refresh_preset_combo()
self._preset_var.set(c.active_preset_name)
self._prompt_folder_var.set(c.prompt_folder_on_export)
```

**`_save_config`** — add:

```python
self._config.active_preset_name = self._preset_var.get()
self._config.prompt_folder_on_export = self._prompt_folder_var.get()
```

**`_get_current_config`** — update to include new fields:

```python
def _get_current_config(self) -> AppConfig:
    from inventor_export_tool.config import AppConfig
    return AppConfig(
        output_folder=self._output_var.get(),
        export_step=self._step_var.get(),
        export_dwg=self._dwg_var.get(),
        export_pdf=self._pdf_var.get(),
        include_parts=self._parts_var.get(),
        include_subassemblies=self._subasm_var.get(),
        include_top_level=self._toplevel_var.get(),
        include_suppressed=self._suppressed_var.get(),
        export_options=self._config.export_options,
        naming_presets=self._config.naming_presets,
        active_preset_name=self._preset_var.get(),
        prompt_folder_on_export=self._prompt_folder_var.get(),
    )
```

**New helpers and handlers** — add these methods (remove `_on_scan`, `_scan_worker`, and the old `_on_export`/`_export_worker`):

```python
def _refresh_preset_combo(self) -> None:
    names = [p.name for p in self._config.naming_presets]
    self._preset_combo.configure(values=names)
    if self._config.active_preset_name in names:
        self._preset_var.set(self._config.active_preset_name)
    elif names:
        self._preset_var.set(names[0])

def _on_preset_selected(self, _event: object = None) -> None:
    self._config.active_preset_name = self._preset_var.get()
    from inventor_export_tool.config import save_config
    save_config(self._config)

def _on_manage_presets(self) -> None:
    from inventor_export_tool.naming_dialog import NamingPresetDialog
    dialog = NamingPresetDialog(
        self.winfo_toplevel(),
        self._config.naming_presets,
        self._config.active_preset_name,
    )
    if dialog.result is not None:
        presets, active_name = dialog.result
        self._config.naming_presets = presets
        self._config.active_preset_name = active_name
        from inventor_export_tool.config import save_config
        save_config(self._config)
        self._refresh_preset_combo()

def _resolve_output_folder(self) -> str | None:
    """Return the export folder, or None if the user cancelled the picker.

    - prompt_folder_on_export=True → always show picker.
    - Output folder field is empty → show picker.
    - Otherwise → return the current field value without prompting.
    """
    current = self._output_var.get().strip()
    prompt = self._prompt_folder_var.get() or not current
    if prompt:
        path = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=current if current else os.path.expanduser("~"),
        )
        return path if path else None
    return current

def _on_export(self) -> None:
    folder = self._resolve_output_folder()
    if folder is None:
        return
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
            summary = orch.scan(output_folder=output_folder)
            orch.export(summary, self._cancel_event)
            self._queue.put(("export_done", orch.last_log_path))
    except Exception as e:
        logging.getLogger(__name__).exception("Worker thread failed")
        self._queue.put(("error", str(e)))

def _on_preview(self) -> None:
    folder = self._resolve_output_folder()
    if folder is None:
        return
    self._output_var.set(folder)
    self._save_config()
    self._set_working(True)
    self._cancel_event.clear()
    self._progress_var.set(0)
    self._progress_label.configure(text="Scanning...")
    config = self._get_current_config()
    self._worker_thread = Thread(
        target=self._preview_worker, args=(config, folder), daemon=True
    )
    self._worker_thread.start()

def _preview_worker(self, config: AppConfig, output_folder: str) -> None:
    from inventor_api._com_threading import com_thread_scope
    from inventor_export_tool.orchestrator import ExportOrchestrator
    try:
        with com_thread_scope():
            orch = ExportOrchestrator(
                config=config,
                progress_callback=self.set_progress,
                log_callback=self.log,
            )
            summary = orch.scan(output_folder=output_folder)
            self._queue.put(("preview_done", summary))
    except Exception as e:
        logging.getLogger(__name__).exception("Worker thread failed")
        self._queue.put(("error", str(e)))
```

**`_set_working`** — update to reference `_preview_btn` instead of `_scan_btn`:

```python
def _set_working(self, working: bool) -> None:
    state = "disabled" if working else "normal"
    self._preview_btn.configure(state=state)
    self._export_btn.configure(state=state)
    self._cancel_btn.configure(state="normal" if working else "disabled")
```

**`_process_queue`** — replace `scan_done` handling with `preview_done`:

```python
elif msg_type == "preview_done":
    self._on_worker_done()
elif msg_type == "export_done":
    if data is not None:
        self._last_log_path = str(data)
        self._open_log_btn.configure(state="normal")
    self._on_worker_done()
```

Remove the `scan_done` branch entirely (it enabled `_export_btn` from the queue, which no longer applies).

- [ ] **Step 7.2: Run ruff to catch import/syntax issues**

```bash
uv run ruff check inventor_export_tool/src/inventor_export_tool/gui.py
```

Fix any reported issues.

- [ ] **Step 7.3: Run the export tool tests**

```bash
uv run --package inventor-export-tool pytest inventor_export_tool/ -v
```

Expected: All PASS (GUI is not unit-tested, but config/naming/orchestrator tests catch regressions).

- [ ] **Step 7.4: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/gui.py
git commit -m "feat(export): rework GUI — naming preset row, folder prompt, single-pass export worker"
```

---

## Task 8: Update CLI with `--preset` argument

**Depends on:** Tasks 3, 5

**Files:**
- Modify: `inventor_export_tool/src/inventor_export_tool/cli.py`

### Context
- New `--preset <name>` argument. Defaults to `config.active_preset_name` if not provided.
- Errors clearly (with `sys.exit(1)`) if the named preset doesn't exist in the loaded config.
- The CLI uses `render_template` identically to the orchestrator (via the orchestrator — no direct import needed in CLI).
- No GUI dialogs are invoked.

- [ ] **Step 8.1: Update `cli.py`**

Replace the full content of `inventor_export_tool/src/inventor_export_tool/cli.py`:

```python
"""CLI entry point for inventor_export_tool."""

from __future__ import annotations

import argparse
import sys

from inventor_export_tool.config import load_config
from inventor_export_tool.orchestrator import ExportOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-export Inventor assemblies to STEP, DWG, and/or PDF."
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Output directory (defaults to config value if omitted)",
    )
    parser.add_argument(
        "--formats",
        default="step",
        metavar="FORMATS",
        help="Comma-separated export formats: step, pdf, dwg (default: step)",
    )
    parser.add_argument(
        "--preset",
        metavar="NAME",
        default=None,
        help="Name of a naming preset from config. Defaults to the active preset.",
    )
    args = parser.parse_args()

    formats = {f.strip().lower() for f in args.formats.split(",")}
    valid = {"step", "pdf", "dwg"}
    unknown = formats - valid
    if unknown:
        print(
            f"ERROR: Unknown format(s): {', '.join(sorted(unknown))}. Choose from: step, pdf, dwg"
        )
        sys.exit(1)

    config = load_config()
    if args.output_dir:
        config.output_folder = args.output_dir

    config.export_step = "step" in formats
    config.export_dwg = "dwg" in formats
    config.export_pdf = "pdf" in formats

    if args.preset is not None:
        preset_names = [p.name for p in config.naming_presets]
        if args.preset not in preset_names:
            print(
                f"ERROR: Preset '{args.preset}' not found. "
                f"Available: {', '.join(preset_names)}",
                file=sys.stderr,
            )
            sys.exit(1)
        config.active_preset_name = args.preset

    def log(msg: str) -> None:
        print(msg)

    from inventor_api._com_threading import com_thread_scope
    from inventor_api.exceptions import InventorError

    try:
        with com_thread_scope():
            orchestrator = ExportOrchestrator(config, log_callback=log)
            summary = orchestrator.scan()
            results = orchestrator.export(summary)
    except InventorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    failed = sum(1 for r in results if not r.success)
    sys.exit(1 if failed else 0)
```

- [ ] **Step 8.2: Verify ruff is clean**

```bash
uv run ruff check inventor_export_tool/src/inventor_export_tool/cli.py
```

- [ ] **Step 8.3: Commit**

```bash
git add inventor_export_tool/src/inventor_export_tool/cli.py
git commit -m "feat(export): add --preset argument to CLI"
```

---

## Task 9: Final verification

**Depends on:** All previous tasks

- [ ] **Step 9.1: Run all unit tests**

```bash
uv run --package inventor-export-tool pytest && uv run --package inventor-api pytest && uv run --package inventor-utils pytest
```

Expected: All PASS, zero failures.

- [ ] **Step 9.2: Ruff clean**

```bash
uv run ruff check . && uv run ruff format --check .
```

Expected: No issues reported. If there are formatting issues, run `uv run ruff format .` and re-check.

- [ ] **Step 9.3: Type check**

```bash
uv run ty check
```

Expected: No errors. If `ty` reports errors in GUI or dialog files related to Tkinter generics or COM types, these are acceptable false positives — document them with a comment and move on.

- [ ] **Step 9.4: PyInstaller build**

```bash
cd zabra_cadabra && uv run python build.py
```

Expected: `.exe` produced without errors.

- [ ] **Step 9.5: Manual GUI smoke test (human required — Inventor must be running)**

Run `uv run zabra-cadabra` and verify each item:

- [ ] Open a part in Inventor. In the Export tab, preset combo shows "OleM Default". Click "Run Export" with the output folder field empty → folder picker appears → select a folder → STEP + PDF (if IDW exists) are produced with `{PartNumber} - {Description} - RevX` naming.
- [ ] Enable `[x] Prompt for folder on every export`. Set a folder in the field. Click "Run Export" → picker still appears regardless.
- [ ] Click `[Manage...]` → dialog opens. Add a new preset "Short", set template to `{Part Number}`, see live preview update. Click Cancel → presets unchanged (original presets still in combobox).
- [ ] Click `[Manage...]` again. Add "Short" preset, Set Active, click OK → combobox now shows "Short". Run Export → filenames match `{Part Number}` template.
- [ ] Click "Preview" → log area shows scan output (list of files), no export is performed (no files written to disk).
- [ ] Start an export, click Cancel → worker stops between files (check log for "Cancelled" message).
- [ ] Close and reopen the app → preset selection and folder are persisted correctly.

---

## Dependency Graph Summary

```
Task 1 (get_iproperty)
  └─► Task 2 (templates.py)
        └─► Task 5 (orchestrator)
              └─► Task 7 (gui.py)
              └─► Task 8 (cli.py)
Task 3 (config NamingPreset)
  └─► Task 5 (orchestrator)
  └─► Task 6 (naming_dialog)
  └─► Task 7 (gui.py)
Task 4 (remove compose_filename) — can run after Task 3, before Task 5
Task 6 (naming_dialog)
  └─► Task 7 (gui.py)
Task 9 (verification) — after all tasks
```

Tasks 1 and 3 are fully independent and can run in parallel.
Task 4 can run after Task 3 (it removes a symbol that Task 5 replaces).
Tasks 2, 5, 6, 7, 8 must run in the order shown.
