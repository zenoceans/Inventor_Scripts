"""Tests for inventor_export_tool.config."""

from inventor_export_tool.config import AppConfig, load_config, save_config


class TestAppConfigDefaults:
    def test_defaults(self):
        c = AppConfig()
        assert c.output_folder == ""
        assert c.export_step is True
        assert c.export_dwg is True
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
