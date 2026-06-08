"""Best-effort reader for the Windows shell 'last visited folder' MRU.

Windows records, per executable, the folder last opened in a common file
dialog under the ComDlg32\\LastVisitedPidlMRU registry key. The MRUListEx
value orders entries by recency across all applications, so the top entry's
trailing PIDL is the folder most recently used by any program.
"""

from __future__ import annotations

import ctypes
import os
import winreg

_MRU_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer"
    r"\ComDlg32\LastVisitedPidlMRU"
)


def get_last_used_folder() -> str | None:
    """Return the folder most recently used by any app's file dialog, or None.

    Returns None on any failure, or if the resolved path is not an existing
    directory. The registry layout is undocumented, so every failure mode
    falls back to None.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _MRU_KEY) as key:
            order, _ = winreg.QueryValueEx(key, "MRUListEx")
            first = int.from_bytes(order[0:4], "little")
            if first == 0xFFFFFFFF:
                return None
            entry, _ = winreg.QueryValueEx(key, str(first))
        path = _pidl_to_path(_strip_exe_name(entry))
        if path and os.path.isdir(path):
            return path
        return None
    except Exception:
        return None


def _strip_exe_name(entry: bytes) -> bytes:
    """Skip the leading null-terminated UTF-16 exe name, return the PIDL bytes."""
    i = 0
    while i + 1 < len(entry):
        if entry[i] == 0 and entry[i + 1] == 0:
            return entry[i + 2 :]
        i += 2
    return entry


def _pidl_to_path(pidl: bytes) -> str | None:
    buf = ctypes.create_unicode_buffer(260)
    pidl_buf = ctypes.create_string_buffer(pidl, len(pidl))
    ok = ctypes.windll.shell32.SHGetPathFromIDListW(pidl_buf, buf)
    return buf.value or None if ok else None
