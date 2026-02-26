"""Zabra-Cadabra shell — main window with header, notebook, and theme."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any

from zabra_cadabra.tab_registry import TABS
from zabra_cadabra.theme import HEADER_BG, HEADER_FG, apply_bw_theme


class ZabraApp:
    """Top-level application shell."""

    def __init__(
        self,
        configs: dict[str, Any],
        session: Any = None,
        telemetry_config: Any = None,
        log_file: Any = None,
        transport: Any = None,
    ) -> None:
        self._configs = configs
        self._session = session
        self._telemetry_config = telemetry_config
        self._log_file = log_file
        self._transport = transport
        self._tabs: list[ttk.Frame] = []

        self._root = tk.Tk()
        self._root.title("Zabra-Cadabra")
        self._root.minsize(800, 600)
        self._root.resizable(True, True)
        self._root.configure(bg="#ffffff")

        # Apply B&W theme before building widgets
        style = ttk.Style(self._root)
        apply_bw_theme(style)

        # Window icon
        self._logo_img: tk.PhotoImage | None = None
        self._logo_header_img: tk.PhotoImage | None = None
        self._load_logo()

        self._build_header()
        self._build_notebook()

        # Telemetry hooks
        if self._telemetry_config and self._telemetry_config.auto_popup_on_error:
            from zabra_cadabra.telemetry.error_hook import install_error_hooks

            install_error_hooks(self._root, self._on_feedback)

        if self._session:
            self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _resolve_asset(self, filename: str) -> str | None:
        if getattr(sys, "frozen", False):
            base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        else:
            base = Path(__file__).resolve().parent.parent
        p = base / filename
        return str(p) if p.exists() else None

    def _load_logo(self) -> None:
        logo_path = self._resolve_asset("Zen LOGO SMUSS.png")
        if not logo_path:
            return
        self._logo_img = tk.PhotoImage(file=logo_path)
        # Header icon: ~40x42px from 201x208
        self._logo_header_img = self._logo_img.subsample(5, 5)
        # Window icon: ~25x26px
        icon_img = self._logo_img.subsample(8, 8)
        self._root.iconphoto(True, icon_img)
        # Keep reference to prevent GC
        self._icon_img = icon_img

    def _build_header(self) -> None:
        header = tk.Frame(self._root, bg=HEADER_BG, height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        if self._logo_header_img:
            tk.Label(header, image=self._logo_header_img, bg=HEADER_BG).pack(
                side="left", padx=(16, 8), pady=8
            )

        tk.Label(
            header,
            text="Zabra-Cadabra",
            bg=HEADER_BG,
            fg=HEADER_FG,
            font=("Segoe UI", 18, "bold"),
        ).pack(side="left", pady=8)

        # Feedback button (right side)
        tk.Button(
            header,
            text="Feedback",
            bg=HEADER_BG,
            fg=HEADER_FG,
            font=("Segoe UI", 9),
            bd=0,
            activebackground=HEADER_BG,
            activeforeground="#cccccc",
            cursor="hand2",
            command=self._on_feedback,
        ).pack(side="right", padx=(0, 16), pady=8)

    def _build_notebook(self) -> None:
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        for spec in TABS:
            config = self._configs.get(spec.config_key) if spec.config_key else None
            tab = spec.factory(self._notebook, config)
            self._notebook.add(tab, text=spec.title)
            self._tabs.append(tab)

    def _on_feedback(self, error_context: dict[str, Any] | None = None) -> None:
        if self._session is None:
            return
        from zabra_cadabra.telemetry.feedback import FeedbackDialog

        FeedbackDialog(
            self._root,
            session=self._session,
            log_file=self._log_file,
            transport=self._transport,
            error_context=error_context,
        )

    def _on_tab_changed(self, _event: object = None) -> None:
        try:
            tab_idx = self._notebook.index(self._notebook.select())
            tab_name = self._notebook.tab(tab_idx, "text")
            logging.getLogger("zabra.shell").info("tab_switch", extra={"data": {"tab": tab_name}})
        except Exception:
            pass

    def run(self) -> None:
        """Start the application main loop."""
        # Kick off polling on tabs that support it
        for tab in self._tabs:
            if hasattr(tab, "start_polling"):
                tab.start_polling()

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.mainloop()

    def _on_close(self) -> None:
        for tab in self._tabs:
            if hasattr(tab, "close"):
                tab.close()
        self._root.destroy()
