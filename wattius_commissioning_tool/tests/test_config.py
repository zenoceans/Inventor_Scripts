from __future__ import annotations

import json
from pathlib import Path

from wattius_commissioning_tool.config import CommissioningConfig, load_config, save_config


def test_default_values():
    config = CommissioningConfig()
    assert config.toolkit_path == ""
    assert config.firmware_path == ""
    assert config.config_path == ""
    assert config.username == ""
    assert config.password == ""
    assert config.remember_password is False
    assert config.can_baudrate == "CAN_500kbps"
    assert config.base_can_node_id == 0
    assert config.ble_mode == "DISABLED"
    assert config.network_mode == "DISABLE"
    assert config.static_ip == "0.0.0.0"
    assert config.netmask == "0.0.0.0"
    assert config.gateway == "0.0.0.0"
    assert config.dns1 == "0.0.0.0"
    assert config.dns2 == "0.0.0.0"
    assert config.manufacturing_date == ""
    assert config.log_directory == "logs"
    assert config.auto_start_on_scan is True


def test_load_config_from_file(tmp_path: Path):
    config_file = tmp_path / "commissioning_config.json"
    data = {
        "toolkit_path": "C:/Tools/toolkit.exe",
        "firmware_path": "C:/firmware.bin",
        "username": "testuser",
        "can_baudrate": "CAN_500kbps",
        "base_can_node_id": 5,
    }
    config_file.write_text(json.dumps(data), encoding="utf-8")

    config = load_config(config_file)

    assert config.toolkit_path == "C:/Tools/toolkit.exe"
    assert config.firmware_path == "C:/firmware.bin"
    assert config.username == "testuser"
    assert config.can_baudrate == "CAN_500kbps"
    assert config.base_can_node_id == 5
    assert config.password == ""  # not in file — gets default


def test_save_config_writes_json(tmp_path: Path):
    config_file = tmp_path / "commissioning_config.json"
    config = CommissioningConfig(
        toolkit_path="C:/tool.exe",
        username="admin",
        remember_password=True,
        password="secret",
    )
    save_config(config, config_file)

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data["toolkit_path"] == "C:/tool.exe"
    assert data["username"] == "admin"
    assert data["remember_password"] is True
    assert data["password"] == "secret"


def test_save_config_omits_password_when_not_remembered(tmp_path: Path):
    config_file = tmp_path / "commissioning_config.json"
    config = CommissioningConfig(
        username="admin",
        password="secret",
        remember_password=False,
    )
    save_config(config, config_file)

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data["password"] == ""


def test_save_config_keeps_password_when_remembered(tmp_path: Path):
    config_file = tmp_path / "commissioning_config.json"
    config = CommissioningConfig(
        username="admin",
        password="secret",
        remember_password=True,
    )
    save_config(config, config_file)

    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert data["password"] == "secret"


def test_load_config_ignores_unknown_keys(tmp_path: Path):
    config_file = tmp_path / "commissioning_config.json"
    data = {
        "toolkit_path": "C:/tool.exe",
        "unknown_future_key": "ignored_value",
        "another_unknown": 42,
    }
    config_file.write_text(json.dumps(data), encoding="utf-8")

    config = load_config(config_file)
    assert config.toolkit_path == "C:/tool.exe"
    assert not hasattr(config, "unknown_future_key")


def test_load_config_missing_file_returns_defaults(tmp_path: Path):
    missing = tmp_path / "does_not_exist.json"
    config = load_config(missing)
    assert isinstance(config, CommissioningConfig)
    assert config.toolkit_path == ""
    assert config.can_baudrate == "CAN_500kbps"


def test_save_config_does_not_mutate_original(tmp_path: Path):
    config_file = tmp_path / "commissioning_config.json"
    config = CommissioningConfig(
        password="secret",
        remember_password=False,
    )
    save_config(config, config_file)
    assert config.password == "secret"  # original unchanged
