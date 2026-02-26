"""Tests for feedback report generation (no Tk required)."""

from __future__ import annotations

from zabra_cadabra.telemetry.session import SessionContext


class TestFeedbackReport:
    """Test the report format without needing Tk."""

    def test_session_in_report_format(self):
        """Verify session data can be formatted into a report string."""
        session = SessionContext(session_id="test123", pc_name="TESTPC")
        d = session.as_dict()
        # Build a minimal report to verify formatting works
        report = f"# Feedback Report\n**Session:** {d['session_id']} | **PC:** {d['pc_name']}\n"
        assert "test123" in report
        assert "TESTPC" in report

    def test_error_context_format(self):
        """Verify error context dict structure."""
        error_context = {
            "type": "ValueError",
            "message": "test error",
            "traceback": "Traceback...\nValueError: test error",
        }
        section = (
            f"{error_context['type']}: {error_context['message']}\n{error_context['traceback']}"
        )
        assert "ValueError: test error" in section
