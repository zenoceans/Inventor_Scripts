"""Modal dialog for choosing which notebook tabs are visible."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class OptionsDialog(tk.Toplevel):
    """Modal dialog to check/uncheck which notebook tabs are visible."""

    def __init__(
        self,
        parent: tk.Misc,
        all_titles: list[str],
        hidden: list[str],
        on_save: Callable[[list[str]], None],
    ) -> None:
        super().__init__(parent)
        self.title("Options")
        self.resizable(False, False)

        self._all_titles = all_titles
        self._hidden = hidden
        self._on_save = on_save
        self._vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()
        self._center_over_parent(parent)
        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.wait_window()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Visible tabs:").pack(anchor="w")

        checks_frame = ttk.Frame(outer, padding=(10, 5))
        checks_frame.pack(fill="both", expand=True)

        for title in self._all_titles:
            var = tk.BooleanVar(value=title not in self._hidden)
            self._vars[title] = var
            ttk.Checkbutton(checks_frame, text=title, variable=var).pack(anchor="w")

        ttk.Label(
            outer,
            text="Restart Zabra-Cadabra for tab changes to take effect.",
            font=("Segoe UI", 8),
            foreground="#666666",
        ).pack(anchor="w", pady=(10, 0))

        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy, width=10).pack(side="right")
        ttk.Button(btn_frame, text="OK", command=self._on_ok, width=10).pack(
            side="right", padx=(0, 5)
        )

    def _on_ok(self) -> None:
        hidden = [title for title, var in self._vars.items() if not var.get()]
        self._on_save(hidden)
        self.destroy()

    def _center_over_parent(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = self.winfo_width()
        dh = self.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        self.geometry(f"+{x}+{y}")
