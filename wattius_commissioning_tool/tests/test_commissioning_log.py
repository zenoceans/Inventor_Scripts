from __future__ import annotations

import csv
from pathlib import Path

import pytest

from wattius_commissioning_tool.commissioning_log import CommissioningLogger
from wattius_commissioning_tool.models import BoardResult


def _make_result(serial: str = "SN001", status: str = "PASS") -> BoardResult:
    return BoardResult(
        serial_number=serial,
        can_node_id=1,
        firmware_version="1.0.0",
        config_crc="0xABCD",
        status=status,
        failure_step=None if status == "PASS" else "connecting",
        failure_reason=None if status == "PASS" else "Connection refused",
        started_at="2026-03-19T10:00:00",
        completed_at="2026-03-19T10:01:00",
    )


def test_start_session_creates_file(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    logger.start_session()

    assert logger.session_path is not None
    session_file = Path(logger.session_path)
    assert session_file.exists()

    # Check header row
    rows = list(csv.reader(session_file.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == CommissioningLogger.COLUMNS


def test_log_board_appends_row(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    logger.start_session()

    result = _make_result("SN001", "PASS")
    logger.log_board(result)

    session_file = Path(logger.session_path)
    rows = list(csv.reader(session_file.read_text(encoding="utf-8").splitlines()))

    assert len(rows) == 2  # header + 1 data row
    assert rows[1][0] == "SN001"
    assert rows[1][4] == "PASS"


def test_multiple_boards(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    logger.start_session()

    for i in range(3):
        logger.log_board(_make_result(f"SN{i:03d}", "PASS"))

    session_file = Path(logger.session_path)
    rows = list(csv.reader(session_file.read_text(encoding="utf-8").splitlines()))

    assert len(rows) == 4  # 1 header + 3 data rows
    assert rows[1][0] == "SN000"
    assert rows[2][0] == "SN001"
    assert rows[3][0] == "SN002"


def test_log_board_before_session_raises(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    with pytest.raises(RuntimeError, match="No active session"):
        logger.log_board(_make_result())


def test_end_session_returns_path(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    logger.start_session()
    path = logger.end_session()

    assert path == logger.session_path
    assert path.endswith(".csv")


def test_end_session_before_start_raises(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    with pytest.raises(RuntimeError, match="No active session"):
        logger.end_session()


def test_session_path_property_none_before_start(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    assert logger.session_path is None


def test_session_path_property_set_after_start(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    logger.start_session()
    assert logger.session_path is not None
    assert "commissioning_" in logger.session_path
    assert logger.session_path.endswith(".csv")


def test_start_session_creates_directory(tmp_path: Path):
    log_dir = tmp_path / "nested" / "logs"
    logger = CommissioningLogger(str(log_dir))
    logger.start_session()

    assert log_dir.exists()
    assert Path(logger.session_path).exists()


def test_log_board_fail_result(tmp_path: Path):
    logger = CommissioningLogger(str(tmp_path))
    logger.start_session()

    result = _make_result("SN001", "FAIL")
    logger.log_board(result)

    session_file = Path(logger.session_path)
    rows = list(csv.reader(session_file.read_text(encoding="utf-8").splitlines()))

    assert rows[1][4] == "FAIL"
    assert rows[1][5] == "connecting"
    assert rows[1][6] == "Connection refused"
