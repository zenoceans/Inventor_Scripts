"""COM threading utilities for Inventor API."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator


@contextmanager
def com_thread_scope() -> Generator[None, None, None]:
    """Initialize COM for the current thread and clean up on exit.

    Use this when calling Inventor COM from a non-main thread (e.g., a
    background worker thread in a GUI app).

    Example::

        with com_thread_scope():
            app = InventorApp.connect()
            # ... do COM work ...
    """
    import pythoncom

    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()
