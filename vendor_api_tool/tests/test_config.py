"""Tests for vendor_api_tool.config."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from vendor_api_tool.config import (
    VendorApiConfig,
    load_vendor_api_config,
    save_vendor_api_config,
)


class TestVendorApiConfigRoundTrip:
    def test_round_trip(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        original = VendorApiConfig(
            nexar_client_id="nx_id",
            nexar_client_secret="nx_secret",
            digikey_client_id="dk_id",
            digikey_client_secret="dk_secret",
            last_mpns=["LM358", "NE555P"],
        )
        save_vendor_api_config(original, path)
        loaded = load_vendor_api_config(path)
        assert loaded.nexar_client_id == "nx_id"
        assert loaded.nexar_client_secret == "nx_secret"
        assert loaded.digikey_client_id == "dk_id"
        assert loaded.digikey_client_secret == "dk_secret"
        assert loaded.last_mpns == ["LM358", "NE555P"]

    def test_saves_valid_json(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        save_vendor_api_config(VendorApiConfig(nexar_client_id="check"), path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["nexar_client_id"] == "check"

    def test_overwrites_existing(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        save_vendor_api_config(VendorApiConfig(nexar_client_id="first"), path)
        save_vendor_api_config(VendorApiConfig(nexar_client_id="second"), path)
        loaded = load_vendor_api_config(path)
        assert loaded.nexar_client_id == "second"


class TestVendorApiConfigMissingFile:
    def test_missing_file_returns_defaults(self, tmp_path: Path):
        config = load_vendor_api_config(tmp_path / "nonexistent.json")
        assert config == VendorApiConfig()

    def test_defaults_are_empty_strings(self, tmp_path: Path):
        config = load_vendor_api_config(tmp_path / "nonexistent.json")
        assert config.nexar_client_id == ""
        assert config.nexar_client_secret == ""
        assert config.digikey_client_id == ""
        assert config.digikey_client_secret == ""
        assert config.last_mpns == []


class TestVendorApiConfigEnvOverride:
    def test_nexar_client_id_env_override(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        save_vendor_api_config(VendorApiConfig(nexar_client_id="from_file"), path)
        with patch.dict("os.environ", {"NEXAR_CLIENT_ID": "from_env"}):
            config = load_vendor_api_config(path)
        assert config.nexar_client_id == "from_env"

    def test_nexar_client_secret_env_override(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        save_vendor_api_config(VendorApiConfig(nexar_client_secret="from_file"), path)
        with patch.dict("os.environ", {"NEXAR_CLIENT_SECRET": "from_env"}):
            config = load_vendor_api_config(path)
        assert config.nexar_client_secret == "from_env"

    def test_digikey_client_id_env_override(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        save_vendor_api_config(VendorApiConfig(digikey_client_id="from_file"), path)
        with patch.dict("os.environ", {"DIGIKEY_CLIENT_ID": "from_env"}):
            config = load_vendor_api_config(path)
        assert config.digikey_client_id == "from_env"

    def test_digikey_client_secret_env_override(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        save_vendor_api_config(VendorApiConfig(digikey_client_secret="from_file"), path)
        with patch.dict("os.environ", {"DIGIKEY_CLIENT_SECRET": "from_env"}):
            config = load_vendor_api_config(path)
        assert config.digikey_client_secret == "from_env"

    def test_env_override_does_not_affect_unset_vars(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        save_vendor_api_config(VendorApiConfig(nexar_client_id="from_file"), path)
        with patch.dict("os.environ", {}, clear=False):
            config = load_vendor_api_config(path)
        assert config.nexar_client_id == "from_file"

    def test_all_env_overrides_at_once(self, tmp_path: Path):
        path = tmp_path / "vendor_api_config.json"
        save_vendor_api_config(VendorApiConfig(), path)
        env = {
            "NEXAR_CLIENT_ID": "nx_id_env",
            "NEXAR_CLIENT_SECRET": "nx_sec_env",
            "DIGIKEY_CLIENT_ID": "dk_id_env",
            "DIGIKEY_CLIENT_SECRET": "dk_sec_env",
        }
        with patch.dict("os.environ", env):
            config = load_vendor_api_config(path)
        assert config.nexar_client_id == "nx_id_env"
        assert config.nexar_client_secret == "nx_sec_env"
        assert config.digikey_client_id == "dk_id_env"
        assert config.digikey_client_secret == "dk_sec_env"
