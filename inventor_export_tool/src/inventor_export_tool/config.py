"""Load and save user preferences as JSON."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from inventor_utils.config import get_config_path, save_dataclass_config

_DEFAULT_PRESET_NAME = "OleM Default"
_DEFAULT_PRESET_TEMPLATE = "{Part Number} - {Description} - Rev{Revision Number}"


class FolderDefaultMode(str, Enum):
    """Where the output-folder picker's initial directory comes from."""

    LAST_EXPORT = "last_export"
    WINDOWS_RECENT = "windows_recent"


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
    excluded_filename_prefixes: list[str] = field(default_factory=list)
    export_options: dict[str, dict[str, Any]] = field(default_factory=dict)
    naming_presets: list[NamingPreset] = field(
        default_factory=lambda: [NamingPreset(_DEFAULT_PRESET_NAME, _DEFAULT_PRESET_TEMPLATE)]
    )
    active_preset_name: str = _DEFAULT_PRESET_NAME
    prompt_folder_on_export: bool = False
    folder_default_mode: FolderDefaultMode = FolderDefaultMode.LAST_EXPORT

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
        "output_folder",
        "export_step",
        "export_dwg",
        "export_pdf",
        "include_parts",
        "include_subassemblies",
        "include_top_level",
        "include_suppressed",
        "excluded_filename_prefixes",
        "export_options",
        "active_preset_name",
        "prompt_folder_on_export",
        "folder_default_mode",
    }
    kwargs: dict[str, Any] = {k: v for k, v in data.items() if k in scalar_fields}

    # Convert naming_presets from list[dict] to list[NamingPreset]
    raw_presets = data.get("naming_presets", [])
    if isinstance(raw_presets, list) and raw_presets:
        presets: list[NamingPreset] = []
        for item in raw_presets:
            if isinstance(item, dict) and "name" in item and "template" in item:
                presets.append(
                    NamingPreset(name=str(item["name"]), template=str(item["template"]))
                )
        kwargs["naming_presets"] = presets if presets else _default_presets()
    else:
        kwargs["naming_presets"] = _default_presets()

    raw_mode = kwargs.get("folder_default_mode")
    if raw_mode is not None:
        try:
            kwargs["folder_default_mode"] = FolderDefaultMode(raw_mode)
        except ValueError:
            kwargs.pop("folder_default_mode")

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
