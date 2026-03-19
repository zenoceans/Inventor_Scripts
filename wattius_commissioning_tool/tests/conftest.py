from __future__ import annotations

from enum import Enum

import pytest


class MockWbmsResult(Enum):
    OK = 0
    ERROR = 1
    TIMEOUT = 2
    GETTING = 3
    WAITING = 4


class MockCanBaudrate(Enum):
    CAN_500kbps = 5


class MockBleMode(Enum):
    ENABLED = 0
    DISABLED = 1


class MockNetworkMode(Enum):
    DISABLE = 0
    STATIC_IP = 1
    DHCP = 2


@pytest.fixture
def mock_wbms_result():
    return MockWbmsResult


@pytest.fixture
def mock_wbms_types():
    return {
        "wbms_result": MockWbmsResult,
        "wbms_can_baudrate": MockCanBaudrate,
        "wbms_ble_mode": MockBleMode,
        "wbms_network_mode": MockNetworkMode,
    }
