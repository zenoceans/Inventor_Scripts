"""Tests for inventor_simplify_tool.config."""

import json

from inventor_simplify_tool.config import (
    SimplifyConfig,
    load_simplify_config,
    save_simplify_config,
)


class TestSimplifyConfigDefaults:
    def test_defaults(self) -> None:
        config = SimplifyConfig()
        assert config.simplify_settings == {}
        assert config.target_assembly_path == ""
        assert config.add_to_assembly is False


class TestLoadSimplifyConfig:
    def test_missing_file(self, tmp_path) -> None:
        config = load_simplify_config(tmp_path / "nope.json")
        assert config == SimplifyConfig()

    def test_corrupt_json(self, tmp_path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("not json!", encoding="utf-8")
        config = load_simplify_config(p)
        assert config == SimplifyConfig()

    def test_non_dict_json(self, tmp_path) -> None:
        p = tmp_path / "arr.json"
        p.write_text("[]", encoding="utf-8")
        config = load_simplify_config(p)
        assert config == SimplifyConfig()

    def test_valid_partial(self, tmp_path) -> None:
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"add_to_assembly": True}), encoding="utf-8")
        config = load_simplify_config(p)
        assert config.add_to_assembly is True
        assert config.simplify_settings == {}

    def test_unknown_fields_ignored(self, tmp_path) -> None:
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"add_to_assembly": True, "unknown_field": 42}), encoding="utf-8")
        config = load_simplify_config(p)
        assert config.add_to_assembly is True
        assert not hasattr(config, "unknown_field")

    def test_round_trip(self, tmp_path) -> None:
        p = tmp_path / "cfg.json"
        original = SimplifyConfig(
            simplify_settings={"remove_internal_bodies": True},
            target_assembly_path=r"C:\test\asm.iam",
            add_to_assembly=True,
        )
        save_simplify_config(original, p)
        loaded = load_simplify_config(p)
        assert loaded == original


class TestSaveSimplifyConfig:
    def test_creates_file(self, tmp_path) -> None:
        p = tmp_path / "cfg.json"
        save_simplify_config(SimplifyConfig(), p)
        assert p.exists()

    def test_overwrites(self, tmp_path) -> None:
        p = tmp_path / "cfg.json"
        save_simplify_config(SimplifyConfig(add_to_assembly=True), p)
        save_simplify_config(SimplifyConfig(add_to_assembly=False), p)
        loaded = load_simplify_config(p)
        assert loaded.add_to_assembly is False
