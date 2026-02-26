"""Tests for TelemetryConfig load/save."""

from __future__ import annotations

import json

from zabra_cadabra.telemetry.config import (
    TelemetryConfig,
    load_telemetry_config,
    save_telemetry_config,
)


class TestTelemetryConfig:
    def test_defaults(self):
        cfg = TelemetryConfig()
        assert cfg.enabled is True
        assert cfg.network_path == ""
        assert cfg.network_sync_enabled is False
        assert cfg.log_level == "INFO"
        assert cfg.auto_popup_on_error is True
        assert cfg.include_username is False

    def test_save_and_load(self, tmp_path):
        path = tmp_path / "telemetry_config.json"
        cfg = TelemetryConfig(enabled=False, log_level="DEBUG")
        save_telemetry_config(cfg, path)
        loaded = load_telemetry_config(path)
        assert loaded.enabled is False
        assert loaded.log_level == "DEBUG"

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        cfg = load_telemetry_config(path)
        assert cfg.enabled is True  # default

    def test_load_corrupt_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json!!!", encoding="utf-8")
        cfg = load_telemetry_config(path)
        assert cfg.enabled is True  # default

    def test_load_ignores_unknown_fields(self, tmp_path):
        path = tmp_path / "tel.json"
        path.write_text(json.dumps({"enabled": False, "unknown_field": 42}), encoding="utf-8")
        cfg = load_telemetry_config(path)
        assert cfg.enabled is False

    def test_save_creates_file(self, tmp_path):
        path = tmp_path / "tel.json"
        save_telemetry_config(TelemetryConfig(), path)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["enabled"] is True
