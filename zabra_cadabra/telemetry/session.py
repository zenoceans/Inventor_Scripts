"""Session context — captures machine/environment metadata at startup."""

from __future__ import annotations

import getpass
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class SessionContext:
    """Immutable snapshot of the runtime environment for a single app session."""

    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pc_name: str = field(default_factory=platform.node)
    username: str = field(default_factory=getpass.getuser)
    os_version: str = field(default_factory=platform.platform)
    python_version: str = field(default_factory=platform.python_version)
    app_version: str = "0.1.0"
    is_frozen: bool = field(default_factory=lambda: bool(getattr(sys, "frozen", False)))
    inventor_version: str = ""

    @classmethod
    def create(cls) -> SessionContext:
        """Create a SessionContext auto-populated from the current runtime environment."""
        return cls(
            session_id=uuid4().hex[:12],
            start_time=datetime.now(timezone.utc).isoformat(),
            pc_name=platform.node(),
            username=getpass.getuser(),
            os_version=platform.platform(),
            python_version=platform.python_version(),
            app_version="0.1.0",
            is_frozen=bool(getattr(sys, "frozen", False)),
            inventor_version="",
        )

    def as_dict(self) -> dict[str, Any]:
        """Return all fields as a plain dictionary suitable for JSON serialization."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "pc_name": self.pc_name,
            "username": self.username,
            "os_version": self.os_version,
            "python_version": self.python_version,
            "app_version": self.app_version,
            "is_frozen": self.is_frozen,
            "inventor_version": self.inventor_version,
        }
