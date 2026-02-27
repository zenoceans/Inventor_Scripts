"""JSONL structured logging with rotating file handler for telemetry."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zabra_cadabra.telemetry.config import TelemetryConfig
    from zabra_cadabra.telemetry.session import SessionContext


class JSONLFormatter(logging.Formatter):
    """Formats log records as single-line JSON strings (JSONL)."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a single-line JSON string for the given log record."""
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        session_id = getattr(record, "session_id", None)
        if session_id is not None:
            payload["session_id"] = session_id

        data = getattr(record, "data", None)
        if isinstance(data, dict):
            payload["data"] = data

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class SessionFilter(logging.Filter):
    """Injects a session_id attribute onto every log record it passes through."""

    def __init__(self, session_id: str) -> None:
        super().__init__()
        self._session_id = session_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = self._session_id
        return True


def setup_logging(config: TelemetryConfig, session: SessionContext) -> Path:
    """Configure the root logger with a rotating JSONL file handler.

    Creates a logs directory next to the executable when frozen, or at the
    project root otherwise. Returns the Path to the log file being written.
    """
    level = getattr(logging, config.log_level.upper(), logging.INFO)

    if getattr(sys, "frozen", False):
        logs_dir = Path(sys.executable).parent / "logs"
    else:
        logs_dir = Path(__file__).resolve().parents[3] / "logs"

    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.fromtimestamp(
        datetime.now(tz=timezone.utc).timestamp(), tz=timezone.utc
    ).strftime("%Y%m%d_%H%M%S")
    pc_name = session.pc_name
    log_file = logs_dir / f"session_{timestamp}_{pc_name}.jsonl"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    handler.setFormatter(JSONLFormatter())
    handler.addFilter(SessionFilter(session.session_id))

    root_logger.addHandler(handler)

    return log_file


def log_event(logger_name: str, event: str, level: int = logging.INFO, **data: Any) -> None:
    """Log a structured event with optional key/value data fields.

    If any keyword arguments are provided they are attached as the `data`
    dict on the log record so that JSONLFormatter can include them.
    """
    logger = logging.getLogger(logger_name)
    if data:
        logger.log(level, event, extra={"data": data})
    else:
        logger.log(level, event)
