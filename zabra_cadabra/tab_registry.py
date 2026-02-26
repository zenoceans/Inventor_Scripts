"""Tab registration for Zabra-Cadabra.

To add a new tool tab, append a ``TabSpec`` to ``TABS``.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Callable


@dataclass
class TabSpec:
    """Specification for a single notebook tab."""

    title: str
    """Label shown on the notebook tab."""

    factory: Callable[[tk.Widget, Any], ttk.Frame]
    """``factory(parent, config) -> Frame`` that builds the tab content."""

    config_key: str | None = None
    """Key into the configs dict passed to ``ZabraApp``. ``None`` means no config."""


def _make_inventor_export_tab(parent: tk.Widget, config: Any) -> ttk.Frame:
    from inventor_export_tool.gui import ExportToolGUI

    return ExportToolGUI(parent, config)


def _make_inventor_simplify_tab(parent: tk.Widget, config: Any) -> ttk.Frame:
    from inventor_simplify_tool.gui import SimplifyToolGUI

    return SimplifyToolGUI(parent, config)


TABS: list[TabSpec] = [
    TabSpec(
        title="Inventor Export",
        factory=_make_inventor_export_tab,
        config_key="inventor_export",
    ),
    TabSpec(
        title="STEP Simplify",
        factory=_make_inventor_simplify_tab,
        config_key="inventor_simplify",
    ),
]
