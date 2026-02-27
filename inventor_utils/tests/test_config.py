"""Tests for inventor_utils.config generic helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from inventor_utils.config import load_dataclass_config, save_dataclass_config


@dataclass
class _SampleConfig:
    name: str = "default"
    count: int = 0
    enabled: bool = True
    tags: list = field(default_factory=list)


class TestLoadDataclassConfig:
    def test_missing_file_returns_defaults(self, tmp_path: Path):
        config = load_dataclass_config(_SampleConfig, tmp_path / "nonexistent.json")
        assert config == _SampleConfig()

    def test_corrupt_json_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text("{not valid json!!!", encoding="utf-8")
        config = load_dataclass_config(_SampleConfig, path)
        assert config == _SampleConfig()

    def test_json_array_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        config = load_dataclass_config(_SampleConfig, path)
        assert config == _SampleConfig()

    def test_empty_json_object_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text("{}", encoding="utf-8")
        config = load_dataclass_config(_SampleConfig, path)
        assert config == _SampleConfig()

    def test_partial_config_uses_defaults_for_missing(self, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text('{"name": "custom", "count": 5}', encoding="utf-8")
        config = load_dataclass_config(_SampleConfig, path)
        assert config.name == "custom"
        assert config.count == 5
        assert config.enabled is True  # default

    def test_ignores_unknown_fields(self, tmp_path: Path):
        path = tmp_path / "config.json"
        path.write_text('{"name": "X", "unknown_field": 42}', encoding="utf-8")
        config = load_dataclass_config(_SampleConfig, path)
        assert config.name == "X"

    def test_all_fields_loaded(self, tmp_path: Path):
        path = tmp_path / "config.json"
        data = {"name": "full", "count": 99, "enabled": False, "tags": ["a", "b"]}
        path.write_text(json.dumps(data), encoding="utf-8")
        config = load_dataclass_config(_SampleConfig, path)
        assert config.name == "full"
        assert config.count == 99
        assert config.enabled is False
        assert config.tags == ["a", "b"]


class TestSaveDataclassConfig:
    def test_creates_file(self, tmp_path: Path):
        path = tmp_path / "config.json"
        assert not path.exists()
        save_dataclass_config(_SampleConfig(), path)
        assert path.exists()

    def test_round_trip(self, tmp_path: Path):
        path = tmp_path / "config.json"
        original = _SampleConfig(name="test", count=7, enabled=False, tags=["x"])
        save_dataclass_config(original, path)
        loaded = load_dataclass_config(_SampleConfig, path)
        assert loaded == original

    def test_overwrites_existing(self, tmp_path: Path):
        path = tmp_path / "config.json"
        save_dataclass_config(_SampleConfig(name="first"), path)
        save_dataclass_config(_SampleConfig(name="second"), path)
        loaded = load_dataclass_config(_SampleConfig, path)
        assert loaded.name == "second"

    def test_saves_valid_json(self, tmp_path: Path):
        path = tmp_path / "config.json"
        save_dataclass_config(_SampleConfig(name="json_check"), path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "json_check"
