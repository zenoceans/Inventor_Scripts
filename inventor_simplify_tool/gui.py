"""STEP Simplify tab — placeholder for GUI agent."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from inventor_simplify_tool.config import SimplifyConfig


class SimplifyToolGUI(ttk.Frame):
    """Placeholder tab for the STEP Import + Simplify tool."""

    def __init__(self, parent: tk.Widget, config: SimplifyConfig | None = None) -> None:
        super().__init__(parent)
        self._config = config or SimplifyConfig()
        ttk.Label(
            self,
            text="STEP Import + Simplify\n\nComing soon.",
            justify="center",
        ).pack(expand=True)
