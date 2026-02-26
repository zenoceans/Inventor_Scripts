"""Tests for JSONL logging setup."""

from __future__ import annotations

import json
import logging

from zabra_cadabra.telemetry.logger import JSONLFormatter, SessionFilter, log_event


class TestJSONLFormatter:
    def test_format_basic_record(self):
        fmt = JSONLFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=None,
            exc_info=None,
        )
        line = fmt.format(record)
        data = json.loads(line)
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["msg"] == "hello world"
        assert "ts" in data

    def test_format_with_session_id(self):
        fmt = JSONLFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="x",
            args=None,
            exc_info=None,
        )
        record.session_id = "abc123"  # type: ignore[attr-defined]
        line = fmt.format(record)
        data = json.loads(line)
        assert data["session_id"] == "abc123"

    def test_format_with_data(self):
        fmt = JSONLFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="ev",
            args=None,
            exc_info=None,
        )
        record.data = {"key": "val"}  # type: ignore[attr-defined]
        line = fmt.format(record)
        data = json.loads(line)
        assert data["data"] == {"key": "val"}

    def test_format_with_exception(self):
        fmt = JSONLFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="err",
            args=None,
            exc_info=exc_info,
        )
        line = fmt.format(record)
        data = json.loads(line)
        assert "exception" in data
        assert "ValueError" in data["exception"]


class TestSessionFilter:
    def test_injects_session_id(self):
        filt = SessionFilter("sess42")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="x",
            args=None,
            exc_info=None,
        )
        result = filt.filter(record)
        assert result is True
        assert record.session_id == "sess42"  # type: ignore[attr-defined]


class TestLogEvent:
    def test_log_event_creates_record(self, caplog):
        with caplog.at_level(logging.INFO, logger="test.events"):
            log_event("test.events", "my_event", key1="val1")
        assert "my_event" in caplog.text
