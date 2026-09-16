"""Zabra-Cadabra shell — main window with header, notebook, and theme."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zabra_cadabra.telemetry.config import TelemetryConfig
    from zabra_cadabra.telemetry.session import SessionContext
    from zabra_cadabra.telemetry.transport import NetworkTransport

from zabra_cadabra.shell_config import ShellConfig
from zabra_cadabra.tab_registry import TABS, TabSpec
from zabra_cadabra.theme import HEADER_BG, HEADER_FG, apply_bw_theme


def filter_visible_tabs(
    specs: list[TabSpec], hidden_tabs: list[str], show_prototypes: bool
) -> list[TabSpec]:
    """Return the subset of specs that should be shown as notebook tabs."""
    return [
        spec
        for spec in specs
        if not (spec.prototype and not show_prototypes) and spec.title not in hidden_tabs
    ]


class ZabraApp:
    """Top-level application shell."""

    def __init__(
        self,
        configs: dict[str, Any],
        session: SessionContext | None = None,
        telemetry_config: TelemetryConfig | None = None,
        log_file: Path | None = None,
        transport: NetworkTransport | None = None,
    ) -> None:
        self._configs = configs
        self._session = session
        self._telemetry_config = telemetry_config
        self._log_file = log_file
        self._transport = transport
        self._shell_config: ShellConfig = self._configs.get("shell") or ShellConfig()
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
            p = base / filename
        else:
            # __file__ is zabra_cadabra/src/zabra_cadabra/shell.py
            # assets live at zabra_cadabra/assets/
            p = Path(__file__).resolve().parent.parent.parent / "assets" / filename
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

        ico_path = self._resolve_asset("Zen LOGO SMUSS.ico")
        if ico_path:
            try:
                self._root.iconbitmap(default=ico_path)
            except Exception:
                pass

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

        # Feedback button (far right)
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

        # Guide button (to the left of Feedback)
        tk.Button(
            header,
            text="Guide",
            bg=HEADER_BG,
            fg=HEADER_FG,
            font=("Segoe UI", 9),
            bd=0,
            activebackground=HEADER_BG,
            activeforeground="#cccccc",
            cursor="hand2",
            command=self._on_guide,
        ).pack(side="right", padx=(0, 8), pady=8)

        # Options button (to the left of Guide)
        tk.Button(
            header,
            text="Options",
            bg=HEADER_BG,
            fg=HEADER_FG,
            font=("Segoe UI", 9),
            bd=0,
            activebackground=HEADER_BG,
            activeforeground="#cccccc",
            cursor="hand2",
            command=self._on_options,
        ).pack(side="right", padx=(0, 8), pady=8)

    def _build_notebook(self) -> None:
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        show_prototypes = self._configs.get("show_prototype_tabs", False)
        visible = filter_visible_tabs(TABS, self._shell_config.hidden_tabs, show_prototypes)
        for spec in visible:
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

    def _on_guide(self) -> None:
        from zabra_cadabra.usage_guide import UsageGuideDialog

        guide_path = self._resolve_asset("usage_guide.txt")
        UsageGuideDialog(self._root, guide_path)

    def _on_options(self) -> None:
        from zabra_cadabra.options_dialog import OptionsDialog

        OptionsDialog(
            self._root,
            all_titles=[t.title for t in TABS],
            hidden=self._shell_config.hidden_tabs,
            on_save=self._on_options_save,
        )

    def _on_options_save(self, hidden_tabs: list[str]) -> None:
        from zabra_cadabra.shell_config import save_shell_config

        self._shell_config.hidden_tabs = hidden_tabs
        save_shell_config(self._shell_config)

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
