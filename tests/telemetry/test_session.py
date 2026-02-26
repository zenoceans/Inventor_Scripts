"""Tests for SessionContext."""

from __future__ import annotations

from zabra_cadabra.telemetry.session import SessionContext


class TestSessionContext:
    def test_create_defaults(self):
        ctx = SessionContext()
        assert len(ctx.session_id) == 12
        assert ctx.pc_name  # non-empty
        assert ctx.python_version  # non-empty
        assert ctx.inventor_version == ""

    def test_as_dict_keys(self):
        ctx = SessionContext()
        d = ctx.as_dict()
        expected_keys = {
            "session_id",
            "start_time",
            "pc_name",
            "username",
            "os_version",
            "python_version",
            "app_version",
            "is_frozen",
            "inventor_version",
        }
        assert set(d.keys()) == expected_keys

    def test_as_dict_values_match(self):
        ctx = SessionContext()
        d = ctx.as_dict()
        assert d["session_id"] == ctx.session_id
        assert d["is_frozen"] == ctx.is_frozen

    def test_custom_fields(self):
        ctx = SessionContext(session_id="abc123", pc_name="TESTPC")
        assert ctx.session_id == "abc123"
        assert ctx.pc_name == "TESTPC"
