"""Tests for PDF diff config loading and saving."""

from __future__ import annotations

from pathlib import Path

from pdf_diff_tool.config import PdfDiffConfig, load_config, save_config


class TestPdfDiffConfig:
    def test_defaults(self):
        config = PdfDiffConfig()
        assert config.dpi == 150
        assert config.open_after_diff is True
        assert config.last_old_path == ""
        assert config.last_new_path == ""

    def test_round_trip(self, tmp_path: Path):
        path = tmp_path / "test_config.json"
        original = PdfDiffConfig(dpi=300, open_after_diff=False, last_old_path="a.pdf")
        save_config(original, path)
        loaded = load_config(path)
        assert loaded.dpi == 300
        assert loaded.open_after_diff is False
        assert loaded.last_old_path == "a.pdf"

    def test_load_missing_file_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        config = load_config(path)
        assert config.dpi == 150
