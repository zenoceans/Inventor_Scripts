"""Tests for the Windows last-used-folder reader."""

from __future__ import annotations

import inventor_utils.recent_folders as rf


def test_strip_exe_name_returns_pidl_after_utf16_terminator():
    # UTF-16LE "ab" + null terminator + PIDL bytes
    entry = b"a\x00b\x00\x00\x00PIDL"
    assert rf._strip_exe_name(entry) == b"PIDL"


def test_get_last_used_folder_returns_none_when_key_missing(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no such key")

    monkeypatch.setattr(rf.winreg, "OpenKey", boom)

    assert rf.get_last_used_folder() is None
