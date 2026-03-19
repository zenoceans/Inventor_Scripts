from __future__ import annotations

import subprocess
import sys
from enum import Enum
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Mock wbms_api into sys.modules BEFORE importing ToolkitManager
# (toolkit_manager.py imports wbms_api at module level)
# ---------------------------------------------------------------------------


class _MockWbmsResult(Enum):
    OK = 0
    ERROR = 1
    TIMEOUT = 2


_mock_sign_in = MagicMock(return_value=_MockWbmsResult.OK)
_mock_poll = MagicMock(return_value=_MockWbmsResult.OK)

_mock_api_mod = MagicMock()
_mock_api_mod.wbms_sign_in = _mock_sign_in
_mock_api_mod.wbms_toolkit_api_poll = _mock_poll

_mock_types_mod = MagicMock()
_mock_types_mod.wbms_result = _MockWbmsResult

sys.modules.setdefault("wbms_api", MagicMock())
sys.modules["wbms_api.wbms_toolkit_api"] = _mock_api_mod
sys.modules["wbms_api.wbms_toolkit_types"] = _mock_types_mod

# Now safe to import
from wattius_commissioning_tool.toolkit_manager import ToolkitManager  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager(**kwargs):
    defaults = dict(toolkit_path="C:/tool.exe", username="admin", password="pass")
    defaults.update(kwargs)
    return ToolkitManager(**defaults)


# ---------------------------------------------------------------------------
# start() tests
# ---------------------------------------------------------------------------


def test_start_launches_process():
    manager = _make_manager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process running after start

    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        manager.start()

    mock_popen.assert_called_once_with(
        ["C:/tool.exe"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def test_start_skips_if_running():
    manager = _make_manager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # already running

    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        manager.start()  # first call
        manager.start()  # second call — should be skipped

    mock_popen.assert_called_once()


# ---------------------------------------------------------------------------
# wait_ready() tests
# ---------------------------------------------------------------------------


def test_wait_ready_returns_true():
    manager = _make_manager()
    _mock_poll.return_value = _MockWbmsResult.OK

    result = manager.wait_ready(timeout=5)

    assert result is True
    _mock_poll.assert_called_with(5)


def test_wait_ready_returns_false():
    manager = _make_manager()
    _mock_poll.return_value = _MockWbmsResult.TIMEOUT

    result = manager.wait_ready(timeout=5)

    assert result is False


# ---------------------------------------------------------------------------
# sign_in() tests
# ---------------------------------------------------------------------------


def test_sign_in_success():
    manager = _make_manager(username="user1", password="secret")
    _mock_sign_in.return_value = _MockWbmsResult.OK

    result = manager.sign_in()

    assert result is True
    _mock_sign_in.assert_called_with("user1", "secret")


def test_sign_in_failure():
    manager = _make_manager(username="user1", password="wrong")
    _mock_sign_in.return_value = _MockWbmsResult.ERROR

    result = manager.sign_in()

    assert result is False


# ---------------------------------------------------------------------------
# stop() tests
# ---------------------------------------------------------------------------


def test_stop_terminates_process():
    manager = _make_manager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # process still running

    with patch("subprocess.Popen", return_value=mock_proc):
        manager.start()

    manager.stop()

    mock_proc.terminate.assert_called_once()


def test_stop_kills_on_timeout():
    manager = _make_manager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    with patch("subprocess.Popen", return_value=mock_proc):
        manager.start()

    mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="C:/tool.exe", timeout=10)

    manager.stop()

    mock_proc.kill.assert_called_once()


def test_stop_does_nothing_if_no_process():
    manager = _make_manager()
    # No start() called — should not raise
    manager.stop()


def test_stop_handles_already_exited_process():
    manager = _make_manager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0  # process already exited

    with patch("subprocess.Popen", return_value=mock_proc):
        manager.start()

    manager.stop()

    # terminate should NOT be called for an already-exited process
    mock_proc.terminate.assert_not_called()


# ---------------------------------------------------------------------------
# is_running() tests
# ---------------------------------------------------------------------------


def test_is_running_returns_false_when_no_process():
    manager = _make_manager()
    assert manager.is_running() is False


def test_is_running_returns_true_when_poll_is_none():
    manager = _make_manager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None  # still running

    with patch("subprocess.Popen", return_value=mock_proc):
        manager.start()

    assert manager.is_running() is True


def test_is_running_returns_false_when_process_exited():
    manager = _make_manager()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0  # process exited

    with patch("subprocess.Popen", return_value=mock_proc):
        manager.start()

    assert manager.is_running() is False
