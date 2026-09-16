"""Tests for inventor_export_tool.config."""

import json

from inventor_export_tool.config import AppConfig, NamingPreset, load_config, save_config


class TestAppConfigDefaults:
    def test_defaults(self):
        c = AppConfig()
        assert c.output_folder == ""
        assert c.export_step is True
        assert c.export_dwg is True
        assert c.export_dxf is True
        assert c.export_pdf is True
        assert c.include_parts is True
        assert c.include_subassemblies is True
        assert c.include_top_level is True
        assert c.include_suppressed is False


class TestLoadConfig:
    def test_missing_file(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.json")
        assert config == AppConfig()

    def test_corrupt_json(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{not valid json!!!", encoding="utf-8")
        config = load_config(path)
        assert config == AppConfig()

    def test_json_array_instead_of_object(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        config = load_config(path)
        assert config == AppConfig()

    def test_empty_json_object(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{}", encoding="utf-8")
        config = load_config(path)
        assert config == AppConfig()

    def test_partial_config(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(
            '{"output_folder": "C:\\\\exports", "export_step": false}', encoding="utf-8"
        )
        config = load_config(path)
        assert config.output_folder == "C:\\exports"
        assert config.export_step is False
        # Other fields should be defaults
        assert config.export_dwg is True
        assert config.export_dxf is True

    def test_ignores_unknown_fields(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text('{"output_folder": "X", "unknown_field": 42}', encoding="utf-8")
        config = load_config(path)
        assert config.output_folder == "X"


class TestSaveConfig:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "config.json"
        original = AppConfig(
            output_folder=r"C:\exports",
            export_step=False,
            include_suppressed=True,
        )
        save_config(original, path)
        loaded = load_config(path)
        assert loaded == original

    def test_creates_file(self, tmp_path):
        path = tmp_path / "config.json"
        assert not path.exists()
        save_config(AppConfig(), path)
        assert path.exists()

    def test_overwrites_existing(self, tmp_path):
        path = tmp_path / "config.json"
        save_config(AppConfig(output_folder="first"), path)
        save_config(AppConfig(output_folder="second"), path)
        loaded = load_config(path)
        assert loaded.output_folder == "second"


class TestExportOptions:
    def test_default_is_empty_dict(self):
        c = AppConfig()
        assert c.export_options == {}

    def test_round_trip(self, tmp_path):
        path = tmp_path / "config.json"
        opts = {
            "step": {"ApplicationProtocolType": 3},
            "pdf": {"Vector_Resolution": 400, "All_Color_AS_Black": 0},
        }
        original = AppConfig(export_options=opts)
        save_config(original, path)
        loaded = load_config(path)
        assert loaded.export_options == opts

    def test_missing_key_defaults_to_empty(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text('{"output_folder": "X"}', encoding="utf-8")
        loaded = load_config(path)
        assert loaded.export_options == {}

    def test_get_format_options(self):
        opts = {"step": {"ApplicationProtocolType": 3}}
        c = AppConfig(export_options=opts)
        assert c.export_options.get("step") == {"ApplicationProtocolType": 3}
        assert c.export_options.get("dwg") is None
        assert c.export_options.get("dxf") is None


class TestExcludedFilenamePrefixes:
    def test_default_is_empty_list(self):
        c = AppConfig()
        assert c.excluded_filename_prefixes == []

    def test_round_trip(self, tmp_path):
        path = tmp_path / "config.json"
        original = AppConfig(excluded_filename_prefixes=["DIN", "ISO", "2", "3"])
        save_config(original, path)
        loaded = load_config(path)
        assert loaded.excluded_filename_prefixes == ["DIN", "ISO", "2", "3"]

    def test_missing_key_defaults_to_empty(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text('{"output_folder": "X"}', encoding="utf-8")
        loaded = load_config(path)
        assert loaded.excluded_filename_prefixes == []


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

    got = pick_initialdir(" C:/typed ", FolderDefaultMode.WINDOWS_RECENT, "C:/last", "C:/recent")
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
