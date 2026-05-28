"""Tests for inventor_api._vault_dialog_suppressor."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from inventor_api._vault_dialog_suppressor import (
    DIALOG_RULES,
    match_rule,
    vault_dialog_suppressor,
)


class TestDialogRules:
    def test_check_out_rule_first(self):
        # Reflects the actual feedback rules; if these change the test should fail loudly.
        assert DIALOG_RULES[0] == ("is not checked out", "No", "Vault check-out prompt")

    def test_read_only_rule_second(self):
        assert DIALOG_RULES[1] == ("is read-only or in use", "Yes", "Vault read-only prompt")


class TestMatchRule:
    def test_checkout_prompt_matches(self):
        body = "File '150714.iam' is not checked out. Do you want to check it out?"
        rule = match_rule(body)
        assert rule is not None
        assert rule[1] == "No"

    def test_read_only_prompt_matches(self):
        body = (
            "Component C:\\Vault\\Workspace\\01 - ZENergy\\150714.iam "
            "is read-only or in use. Continue with edit?"
        )
        rule = match_rule(body)
        assert rule is not None
        assert rule[1] == "Yes"

    def test_case_insensitive(self):
        assert match_rule("IS NOT CHECKED OUT") is not None
        assert match_rule("Is Read-Only Or In Use") is not None

    def test_returns_none_on_unrelated_dialog(self):
        assert match_rule("Save changes before closing?") is None
        assert match_rule("") is None
        assert match_rule("Some other unrelated message.") is None

    def test_returns_first_match_when_multiple_could_apply(self):
        # Defensive: even if a dialog body somehow contained both fragments,
        # the check-out rule should win (declared first).
        body = "is not checked out / is read-only or in use"
        rule = match_rule(body)
        assert rule is not None
        assert rule[0] == "is not checked out"


class TestVaultDialogSuppressorContextManager:
    def test_starts_and_stops_thread_cleanly(self):
        scan_counter = {"calls": 0}

        def fake_scan(_on_dismiss):
            scan_counter["calls"] += 1
            return 0

        with patch("inventor_api._vault_dialog_suppressor._scan_once", side_effect=fake_scan):
            initial_thread_count = threading.active_count()
            with vault_dialog_suppressor(poll_interval=0.01):
                # Give the worker a moment to spin up and scan a few times.
                time.sleep(0.05)
                assert threading.active_count() > initial_thread_count
            # After exit, the worker thread should have stopped.
            # Give the join a moment to settle.
            for _ in range(20):
                if threading.active_count() == initial_thread_count:
                    break
                time.sleep(0.02)
            assert threading.active_count() == initial_thread_count
        assert scan_counter["calls"] >= 1

    def test_on_dismiss_callback_forwarded(self):
        seen_messages: list[str] = []

        def fake_scan(on_dismiss):
            if on_dismiss is not None:
                on_dismiss("Auto-dismissed test: clicked 'OK'")
            return 1

        with patch("inventor_api._vault_dialog_suppressor._scan_once", side_effect=fake_scan):
            with vault_dialog_suppressor(on_dismiss=seen_messages.append, poll_interval=0.01):
                # Wait until at least one dismissal has been forwarded.
                deadline = time.monotonic() + 1.0
                while not seen_messages and time.monotonic() < deadline:
                    time.sleep(0.01)
        assert seen_messages, "on_dismiss callback was never invoked"
        assert "Auto-dismissed test" in seen_messages[0]

    def test_scan_exception_does_not_kill_worker(self):
        call_counter = {"n": 0}

        def flaky_scan(_on_dismiss):
            call_counter["n"] += 1
            if call_counter["n"] == 1:
                raise RuntimeError("boom")
            return 0

        with patch("inventor_api._vault_dialog_suppressor._scan_once", side_effect=flaky_scan):
            with vault_dialog_suppressor(poll_interval=0.01):
                deadline = time.monotonic() + 1.0
                while call_counter["n"] < 2 and time.monotonic() < deadline:
                    time.sleep(0.01)
        assert call_counter["n"] >= 2, (
            "Worker stopped after the first failing scan instead of continuing"
        )


class TestNormalizeAndFind:
    """Spot-checks on helpers without invoking real Win32."""

    def test_normalize_button_label_strips_mnemonic(self):
        from inventor_api._vault_dialog_suppressor import _normalize_button_label

        assert _normalize_button_label("&Yes") == "yes"
        assert _normalize_button_label(" No ") == "no"
        assert _normalize_button_label("Yes To &All") == "yes to all"


@pytest.mark.skipif(
    not __import__("sys").platform.startswith("win"),
    reason="Win32 helpers only meaningful on Windows",
)
def test_win32_helpers_are_importable():
    """Smoke test: the module imports cleanly on Windows."""
    from inventor_api import _vault_dialog_suppressor as mod

    assert mod._user32 is not None
    assert mod._EnumWindowsProc is not None
    assert mod._EnumChildProc is not None
