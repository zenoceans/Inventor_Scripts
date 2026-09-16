"""Tests for shell config loading and saving."""

from __future__ import annotations

from pathlib import Path

from zabra_cadabra.shell_config import ShellConfig, load_shell_config, save_shell_config


class TestShellConfig:
    def test_defaults(self):
        config = ShellConfig()
        assert config.hidden_tabs == []

    def test_round_trip(self, tmp_path: Path):
        path = tmp_path / "test_config.json"
        original = ShellConfig(hidden_tabs=["Vendor API", "BMU Commissioning"])
        save_shell_config(original, path)
        loaded = load_shell_config(path)
        assert loaded.hidden_tabs == ["Vendor API", "BMU Commissioning"]

    def test_load_missing_file_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        config = load_shell_config(path)
        assert config.hidden_tabs == []
