"""Configuration for the vendor API tool."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from inventor_utils.config import (
    get_config_path,
    load_dataclass_config,
    save_dataclass_config,
)

_CONFIG_FILENAME = "vendor_api_config.json"


@dataclass
class VendorApiConfig:
    """User-configurable settings for the vendor API tool."""

    nexar_client_id: str = ""
    nexar_client_secret: str = ""
    digikey_client_id: str = ""
    digikey_client_secret: str = ""
    last_mpns: list[str] = field(default_factory=list)


def get_vendor_api_config_path() -> Path:
    return get_config_path(_CONFIG_FILENAME)


def load_vendor_api_config(path: Path | None = None) -> VendorApiConfig:
    if path is None:
        path = get_vendor_api_config_path()
    config = load_dataclass_config(VendorApiConfig, path)
    if val := os.environ.get("NEXAR_CLIENT_ID"):
        config.nexar_client_id = val
    if val := os.environ.get("NEXAR_CLIENT_SECRET"):
        config.nexar_client_secret = val
    if val := os.environ.get("DIGIKEY_CLIENT_ID"):
        config.digikey_client_id = val
    if val := os.environ.get("DIGIKEY_CLIENT_SECRET"):
        config.digikey_client_secret = val
    return config


def save_vendor_api_config(config: VendorApiConfig, path: Path | None = None) -> None:
    if path is None:
        path = get_vendor_api_config_path()
    save_dataclass_config(config, path)
