# CommissioningToolGUI and CommissioningConfig will be implemented in later tasks.
# Lazy imports to avoid hard dependency at import time until those modules exist.

from __future__ import annotations

__all__ = ["CommissioningToolGUI", "CommissioningConfig"]


def __getattr__(name: str) -> object:
    if name == "CommissioningToolGUI":
        from wattius_commissioning_tool.gui import CommissioningToolGUI  # noqa: PLC0415

        return CommissioningToolGUI
    if name == "CommissioningConfig":
        from wattius_commissioning_tool.config import CommissioningConfig  # noqa: PLC0415

        return CommissioningConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
