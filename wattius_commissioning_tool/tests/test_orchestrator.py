from __future__ import annotations

import sys
from enum import Enum
from threading import Event
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Mock wbms_api modules into sys.modules BEFORE importing orchestrator
# ---------------------------------------------------------------------------


class _MockWbmsResult(Enum):
    OK = 0
    ERROR = 1
    TIMEOUT = 2
    GETTING = 3
    WAITING = 4


class _MockCanBaudrate(Enum):
    CAN_500kbps = 5


class _MockBleMode(Enum):
    ENABLED = 0
    DISABLED = 1


class _MockNetworkMode(Enum):
    DISABLE = 0
    STATIC_IP = 1
    DHCP = 2


_mock_toolkit_api = MagicMock()
_mock_toolkit_types = MagicMock()
_mock_toolkit_types.wbms_result = _MockWbmsResult
_mock_toolkit_types.wbms_can_baudrate = _MockCanBaudrate
_mock_toolkit_types.wbms_ble_mode = _MockBleMode
_mock_toolkit_types.wbms_network_mode = _MockNetworkMode

_mock_wbms_api_pkg = MagicMock()
sys.modules.setdefault("wbms_api", _mock_wbms_api_pkg)
sys.modules.setdefault("wbms_api.wbms_toolkit_api", _mock_toolkit_api)
sys.modules.setdefault("wbms_api.wbms_toolkit_types", _mock_toolkit_types)

# Now safe to import
from wattius_commissioning_tool.config import CommissioningConfig  # noqa: E402
from wattius_commissioning_tool.models import CommissioningStep  # noqa: E402
from wattius_commissioning_tool.orchestrator import CommissioningOrchestrator, _zero_pad_ip  # noqa: E402


# ---------------------------------------------------------------------------
# Helper to build a standard config for tests
# ---------------------------------------------------------------------------


def _make_config(**kwargs) -> CommissioningConfig:
    defaults = dict(
        toolkit_path="C:/tool.exe",
        firmware_path="C:/fw.bin",
        config_path="C:/cfg.json",
        username="admin",
        password="pass",
        can_baudrate="CAN_500kbps",
        base_can_node_id=0,
        ble_mode="DISABLED",
        network_mode="DISABLE",
        static_ip="192.168.1.1",
        netmask="255.255.255.0",
        gateway="192.168.1.254",
        dns1="8.8.8.8",
        dns2="8.8.4.4",
        manufacturing_date="2026-03-19",
    )
    defaults.update(kwargs)
    return CommissioningConfig(**defaults)


# ---------------------------------------------------------------------------
# _zero_pad_ip tests
# ---------------------------------------------------------------------------


def test_zero_pad_ip_zeros():
    assert _zero_pad_ip("0.0.0.0") == "000.000.000.000"


def test_zero_pad_ip_mixed():
    assert _zero_pad_ip("192.168.1.1") == "192.168.001.001"


def test_zero_pad_ip_already_padded():
    assert _zero_pad_ip("010.020.030.040") == "010.020.030.040"


# ---------------------------------------------------------------------------
# process_board tests
# ---------------------------------------------------------------------------


def _make_all_pass_api():
    """Return a dict of mock API functions that all succeed."""
    api = {
        "wbms_set_connection_usb": MagicMock(return_value=_MockWbmsResult.OK),
        "wbms_update_firmware": MagicMock(return_value=_MockWbmsResult.OK),
        "wbms_upload_config": MagicMock(return_value=_MockWbmsResult.OK),
        "wbms_apply_setup": MagicMock(return_value=_MockWbmsResult.OK),
        "wbms_get_config_crc": MagicMock(return_value="0xABCD1234"),
    }
    return api


def _run_process_board(
    api_mocks: dict, config: CommissioningConfig | None = None, cancel_event: Event | None = None
):
    if config is None:
        config = _make_config()
    if cancel_event is None:
        cancel_event = Event()

    progress_calls = []
    step_calls = []
    log_calls = []

    orch = CommissioningOrchestrator(
        progress_callback=lambda c, t: progress_calls.append((c, t)),
        log_callback=lambda m: log_calls.append(m),
        step_callback=lambda s, st: step_calls.append((s, st)),
    )

    # Patch deferred imports inside orchestrator methods
    with (
        patch(
            "wattius_commissioning_tool.orchestrator.wbms_set_connection_usb"
            if False
            else "wbms_api.wbms_toolkit_api.wbms_set_connection_usb",
            api_mocks["wbms_set_connection_usb"],
            create=True,
        ),
        patch.dict(
            sys.modules,
            {
                "wbms_api.wbms_toolkit_api": _build_api_module(api_mocks),
                "wbms_api.wbms_toolkit_types": _mock_toolkit_types,
            },
        ),
    ):
        result = orch.process_board("SN001", 1, config, cancel_event)

    return result, progress_calls, step_calls, log_calls


def _build_api_module(api_mocks: dict) -> MagicMock:
    """Build a mock module object with the given API function mocks."""
    mod = MagicMock()
    mod.wbms_set_connection_usb = api_mocks["wbms_set_connection_usb"]
    mod.wbms_update_firmware = api_mocks["wbms_update_firmware"]
    mod.wbms_upload_config = api_mocks["wbms_upload_config"]
    mod.wbms_apply_setup = api_mocks["wbms_apply_setup"]
    mod.wbms_get_config_crc = api_mocks["wbms_get_config_crc"]
    return mod


def _run_board(
    api_mocks: dict, config: CommissioningConfig | None = None, cancel_event: Event | None = None
):
    if config is None:
        config = _make_config()
    if cancel_event is None:
        cancel_event = Event()

    progress_calls: list = []
    step_calls: list = []
    log_calls: list = []

    orch = CommissioningOrchestrator(
        progress_callback=lambda c, t: progress_calls.append((c, t)),
        log_callback=lambda m: log_calls.append(m),
        step_callback=lambda s, st: step_calls.append((s, st)),
    )

    api_module = _build_api_module(api_mocks)
    with patch.dict(
        sys.modules,
        {
            "wbms_api.wbms_toolkit_api": api_module,
            "wbms_api.wbms_toolkit_types": _mock_toolkit_types,
        },
    ):
        result = orch.process_board("SN001", 1, config, cancel_event)

    return result, progress_calls, step_calls, log_calls


def test_process_board_all_pass():
    api = _make_all_pass_api()
    result, progress_calls, step_calls, _ = _run_board(api)

    assert result.status == "PASS"
    assert result.serial_number == "SN001"
    assert result.can_node_id == 1
    assert result.config_crc == "0xABCD1234"
    assert result.failure_step is None
    assert result.failure_reason is None
    assert result.started_at != ""
    assert result.completed_at != ""

    # 6 progress calls, one per step
    assert len(progress_calls) == 6
    assert progress_calls[0] == (1, 6)
    assert progress_calls[-1] == (6, 6)


def test_process_board_connect_fail():
    api = _make_all_pass_api()
    api["wbms_set_connection_usb"] = MagicMock(return_value=_MockWbmsResult.ERROR)

    result, _, step_calls, _ = _run_board(api)

    assert result.status == "FAIL"
    assert result.failure_step == CommissioningStep.CONNECTING.value
    assert "wbms_set_connection_usb" in result.failure_reason

    # step callback should have "running" and "fail" for CONNECTING
    connecting_calls = [(s, st) for s, st in step_calls if s == CommissioningStep.CONNECTING]
    statuses = [st for _, st in connecting_calls]
    assert "running" in statuses
    assert "fail" in statuses


def test_process_board_flash_fail():
    api = _make_all_pass_api()
    api["wbms_update_firmware"] = MagicMock(return_value=_MockWbmsResult.ERROR)

    result, _, _, _ = _run_board(api)

    assert result.status == "FAIL"
    assert result.failure_step == CommissioningStep.FLASHING.value


def test_process_board_config_timeout():
    # upload_config always returns WAITING — will hit TimeoutError in _poll_until_done
    # We need to speed up the timeout; patch time.sleep and time.monotonic
    call_count = [0]

    def fast_upload_config(_path):
        call_count[0] += 1
        return _MockWbmsResult.WAITING

    api = _make_all_pass_api()
    api["wbms_upload_config"] = fast_upload_config

    import time as _time_mod

    start_time = [0.0]

    def mock_monotonic():
        # Return increasing values to simulate time passing quickly
        start_time[0] += 50.0
        return start_time[0]

    orch = CommissioningOrchestrator()
    cancel_event = Event()
    config = _make_config()
    api_module = _build_api_module(api)

    with (
        patch.dict(
            sys.modules,
            {
                "wbms_api.wbms_toolkit_api": api_module,
                "wbms_api.wbms_toolkit_types": _mock_toolkit_types,
            },
        ),
        patch.object(_time_mod, "sleep"),
        patch.object(_time_mod, "monotonic", mock_monotonic),
    ):
        result = orch.process_board("SN001", 1, config, cancel_event)

    assert result.status == "FAIL"
    assert result.failure_step == CommissioningStep.CONFIGURING.value
    assert "timed out" in result.failure_reason


def test_process_board_cancel():
    api = _make_all_pass_api()
    cancel_event = Event()
    cancel_event.set()  # pre-cancelled

    result, _, _, _ = _run_board(api, cancel_event=cancel_event)

    assert result.status == "FAIL"
    assert result.failure_reason == "cancelled"


def test_process_board_crc_returned():
    api = _make_all_pass_api()
    crc_call_count = [0]

    def get_crc_after_waiting():
        crc_call_count[0] += 1
        if crc_call_count[0] < 2:
            return _MockWbmsResult.WAITING
        return "0xDEADBEEF"

    api["wbms_get_config_crc"] = get_crc_after_waiting

    import time as _time_mod

    orch = CommissioningOrchestrator()
    cancel_event = Event()
    config = _make_config()
    api_module = _build_api_module(api)

    with (
        patch.dict(
            sys.modules,
            {
                "wbms_api.wbms_toolkit_api": api_module,
                "wbms_api.wbms_toolkit_types": _mock_toolkit_types,
            },
        ),
        patch.object(_time_mod, "sleep"),
    ):
        result = orch.process_board("SN001", 1, config, cancel_event)

    assert result.status == "PASS"
    assert result.config_crc == "0xDEADBEEF"


def test_process_board_step_callbacks():
    api = _make_all_pass_api()
    step_calls: list = []

    orch = CommissioningOrchestrator(
        step_callback=lambda s, st: step_calls.append((s, st)),
    )
    cancel_event = Event()
    config = _make_config()
    api_module = _build_api_module(api)

    with patch.dict(
        sys.modules,
        {
            "wbms_api.wbms_toolkit_api": api_module,
            "wbms_api.wbms_toolkit_types": _mock_toolkit_types,
        },
    ):
        result = orch.process_board("SN001", 1, config, cancel_event)

    assert result.status == "PASS"

    # All 6 steps should have "running" and "pass" callbacks
    for step in CommissioningStep:
        calls_for_step = [(s, st) for s, st in step_calls if s == step]
        statuses = [st for _, st in calls_for_step]
        assert "running" in statuses, f"Missing 'running' for {step}"
        assert "pass" in statuses, f"Missing 'pass' for {step}"
