"""Auto-dismiss known Inventor / Vault blocking dialogs during batch automation.

The Vault add-in raises modal dialogs that cannot be suppressed via the Inventor
COM API (``SilentOperation`` / ``UserInteractionDisabled`` only cover translator
warnings). To run unattended, a daemon thread polls top-level windows and
clicks the chosen button on any matching dialog.

Currently handled:

- "File 'X.iam' is not checked out. Do you want to check it out?" -> click No
- "Component '...' is read-only or in use. Continue with edit?"  -> click Yes

Usage::

    from inventor_api._vault_dialog_suppressor import vault_dialog_suppressor

    with vault_dialog_suppressor(on_dismiss=log.info):
        # run batch automation
        ...
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from contextlib import contextmanager
from ctypes import wintypes
from typing import Callable, Generator

_log = logging.getLogger("inventor_api.vault_dialog")

# Rule = (text-fragment to match in dialog body, button label to click, log description).
# Matching is case-insensitive and substring-based on concatenated static-text controls.
DialogRule = tuple[str, str, str]

DIALOG_RULES: tuple[DialogRule, ...] = (
    ("is not checked out", "No", "Vault check-out prompt"),
    ("is read-only or in use", "Yes", "Vault read-only prompt"),
)

# Standard Win32 dialog class (used by MessageBox-style modals).
_DIALOG_CLASS = "#32770"

# Win32 message ids
_WM_GETTEXT = 0x000D
_WM_GETTEXTLENGTH = 0x000E
_BM_CLICK = 0x00F5

if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
else:  # pragma: no cover - non-Windows platforms
    _user32 = None
    _EnumWindowsProc = None
    _EnumChildProc = None


def match_rule(body_text: str) -> DialogRule | None:
    """Return the first matching rule for ``body_text``, or None.

    Matching is case-insensitive and substring-based.
    """
    body_lower = body_text.lower()
    for rule in DIALOG_RULES:
        fragment, _, _ = rule
        if fragment.lower() in body_lower:
            return rule
    return None


def _normalize_button_label(label: str) -> str:
    """Strip mnemonic ampersands and whitespace for case-insensitive button comparison."""
    return label.replace("&", "").strip().lower()


def _get_window_text(hwnd: int) -> str:
    length = _user32.SendMessageW(hwnd, _WM_GETTEXTLENGTH, 0, 0)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.SendMessageW(hwnd, _WM_GETTEXT, length + 1, ctypes.byref(buf))
    return buf.value


def _get_class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(64)
    _user32.GetClassNameW(hwnd, buf, 64)
    return buf.value


def _enum_children(hwnd: int) -> list[int]:
    children: list[int] = []

    def cb(child: int, _lparam: int) -> bool:
        children.append(child)
        return True

    _user32.EnumChildWindows(hwnd, _EnumChildProc(cb), 0)
    return children


def _dialog_body_text(hwnd: int) -> str:
    parts: list[str] = []
    for child in _enum_children(hwnd):
        if _get_class_name(child).lower() == "static":
            text = _get_window_text(child)
            if text:
                parts.append(text)
    return " ".join(parts)


def _find_button(hwnd: int, label: str) -> int | None:
    target = _normalize_button_label(label)
    for child in _enum_children(hwnd):
        if _get_class_name(child).lower() != "button":
            continue
        if _normalize_button_label(_get_window_text(child)) == target:
            return child
    return None


def _try_suppress_dialog(hwnd: int, on_dismiss: Callable[[str], None] | None) -> bool:
    """Inspect ``hwnd``; if it matches a rule, click the chosen button and return True."""
    if _get_class_name(hwnd) != _DIALOG_CLASS:
        return False
    if not _user32.IsWindowVisible(hwnd):
        return False
    body = _dialog_body_text(hwnd)
    if not body:
        return False
    rule = match_rule(body)
    if rule is None:
        return False
    _, button_label, description = rule
    btn = _find_button(hwnd, button_label)
    if btn is None:
        return False
    _user32.SendMessageW(btn, _BM_CLICK, 0, 0)
    if on_dismiss is not None:
        try:
            on_dismiss(f"Auto-dismissed {description}: clicked '{button_label}'")
        except Exception:
            _log.exception("on_dismiss callback raised")
    return True


def _scan_once(on_dismiss: Callable[[str], None] | None) -> int:
    """Enumerate top-level windows, suppress any matching dialogs. Returns the count."""
    count = 0

    def cb(hwnd: int, _lparam: int) -> bool:
        nonlocal count
        try:
            if _try_suppress_dialog(hwnd, on_dismiss):
                count += 1
        except Exception:
            _log.exception("Error while inspecting hwnd %s", hwnd)
        return True

    _user32.EnumWindows(_EnumWindowsProc(cb), 0)
    return count


@contextmanager
def vault_dialog_suppressor(
    on_dismiss: Callable[[str], None] | None = None,
    poll_interval: float = 0.15,
) -> Generator[None, None, None]:
    """Run a background watcher that auto-dismisses known Vault dialogs.

    Args:
        on_dismiss: Optional callback invoked with a short description each time
            a dialog is dismissed. Use to surface activity in user-facing logs.
        poll_interval: Seconds between scans. Default 0.15s — short enough that
            dialogs don't linger visibly, low enough not to load the CPU.
    """
    if sys.platform != "win32":  # pragma: no cover - non-Windows platforms
        yield
        return

    stop = threading.Event()

    def worker() -> None:
        while not stop.is_set():
            try:
                n = _scan_once(on_dismiss)
                if n:
                    _log.debug("Suppressed %d Vault dialog(s)", n)
            except Exception:
                _log.exception("Vault dialog suppressor scan failed")
            stop.wait(poll_interval)

    thread = threading.Thread(
        target=worker,
        name="vault-dialog-suppressor",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1.0)


__all__ = ["DIALOG_RULES", "match_rule", "vault_dialog_suppressor"]
