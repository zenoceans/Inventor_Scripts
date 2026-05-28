"""Modal dialog that displays the bundled usage guide."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk


class UsageGuideDialog(tk.Toplevel):
    """Modal dialog showing the contents of ``usage_guide.txt``."""

    def __init__(self, parent: tk.Misc, guide_path: Path | str | None) -> None:
        super().__init__(parent)
        self.title("Usage Guide")
        self.resizable(True, True)
        self.geometry("720x560")

        self._guide_path = guide_path

        self._build_ui()
        self._center_over_parent(parent)
        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.wait_window()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        text = tk.Text(
            text_frame,
            wrap="word",
            font=("Consolas", 10),
            yscrollcommand=scrollbar.set,
        )
        text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text.yview)

        content = self._load_content()
        text.insert("1.0", content)
        text.config(state="disabled")

        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_frame, text="Close", command=self.destroy, width=10).pack(side="right")

    def _load_content(self) -> str:
        if self._guide_path is None:
            return "Usage guide is unavailable."
        try:
            return Path(self._guide_path).read_text(encoding="utf-8")
        except OSError:
            return "Usage guide is unavailable."

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
