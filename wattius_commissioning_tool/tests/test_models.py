from __future__ import annotations

from wattius_commissioning_tool.models import BoardResult, CommissioningStep, SessionState


def test_commissioning_step_values():
    assert CommissioningStep.CONNECTING.value == "connecting"
    assert CommissioningStep.FLASHING.value == "flashing"
    assert CommissioningStep.CONFIGURING.value == "configuring"
    assert CommissioningStep.APPLYING_SETUP.value == "applying_setup"
    assert CommissioningStep.TESTING.value == "testing"
    assert CommissioningStep.LOGGING.value == "logging"


def test_commissioning_step_count():
    assert len(CommissioningStep) == 6


def test_board_result_pass():
    result = BoardResult(
        serial_number="SN001",
        can_node_id=1,
        firmware_version="1.2.3",
        config_crc="0xABCD",
        status="PASS",
        failure_step=None,
        failure_reason=None,
        started_at="2026-03-19T10:00:00",
        completed_at="2026-03-19T10:01:00",
    )
    assert result.serial_number == "SN001"
    assert result.can_node_id == 1
    assert result.firmware_version == "1.2.3"
    assert result.config_crc == "0xABCD"
    assert result.status == "PASS"
    assert result.failure_step is None
    assert result.failure_reason is None


def test_board_result_fail():
    result = BoardResult(
        serial_number="SN002",
        can_node_id=2,
        firmware_version="",
        config_crc=None,
        status="FAIL",
        failure_step="connecting",
        failure_reason="Connection refused",
        started_at="2026-03-19T10:00:00",
        completed_at="2026-03-19T10:00:05",
    )
    assert result.status == "FAIL"
    assert result.failure_step == "connecting"
    assert result.failure_reason == "Connection refused"
    assert result.config_crc is None


def test_session_state_defaults():
    state = SessionState()
    assert state.board_index == 0
    assert state.session_start == ""
    assert state.results == []


def test_session_state_add_results():
    state = SessionState()
    result = BoardResult(
        serial_number="SN001",
        can_node_id=1,
        firmware_version="1.0.0",
        config_crc="0x1234",
        status="PASS",
        failure_step=None,
        failure_reason=None,
        started_at="2026-03-19T10:00:00",
        completed_at="2026-03-19T10:01:00",
    )
    state.results.append(result)
    assert len(state.results) == 1
    assert state.results[0].serial_number == "SN001"


def test_session_state_results_are_independent():
    state1 = SessionState()
    state2 = SessionState()
    result = BoardResult(
        serial_number="SN001",
        can_node_id=1,
        firmware_version="",
        config_crc=None,
        status="PASS",
        failure_step=None,
        failure_reason=None,
        started_at="",
        completed_at="",
    )
    state1.results.append(result)
    assert len(state2.results) == 0
