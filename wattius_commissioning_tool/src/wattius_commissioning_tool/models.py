from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CommissioningStep(Enum):
    CONNECTING = "connecting"
    FLASHING = "flashing"
    CONFIGURING = "configuring"
    APPLYING_SETUP = "applying_setup"
    TESTING = "testing"
    LOGGING = "logging"


@dataclass
class BoardResult:
    serial_number: str
    can_node_id: int
    firmware_version: str
    config_crc: str | None
    status: str
    failure_step: str | None
    failure_reason: str | None
    started_at: str
    completed_at: str


@dataclass
class SessionState:
    board_index: int = 0
    session_start: str = ""
    results: list[BoardResult] = field(default_factory=list)
