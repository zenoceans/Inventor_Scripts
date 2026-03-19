from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from inventor_utils.config import load_dataclass_config, save_dataclass_config


@dataclass
class CommissioningConfig:
    toolkit_path: str = ""
    firmware_path: str = ""
    config_path: str = ""
    username: str = ""
    password: str = ""
    remember_password: bool = False
    can_baudrate: str = "CAN_500kbps"
    base_can_node_id: int = 0
    ble_mode: str = "DISABLED"
    network_mode: str = "DISABLE"
    static_ip: str = "0.0.0.0"
    netmask: str = "0.0.0.0"
    gateway: str = "0.0.0.0"
    dns1: str = "0.0.0.0"
    dns2: str = "0.0.0.0"
    manufacturing_date: str = ""
    log_directory: str = "logs"
    auto_start_on_scan: bool = True


def load_config(path: Path) -> CommissioningConfig:
    return load_dataclass_config(CommissioningConfig, path)


def save_config(config: CommissioningConfig, path: Path) -> None:
    if not config.remember_password:
        config = copy.copy(config)
        config.password = ""
    save_dataclass_config(config, path)
