"""Tkinter GUI tab for the Vendor API Tool."""

from __future__ import annotations

import queue
import tkinter as tk
from threading import Thread
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vendor_api_tool.config import VendorApiConfig


class VendorApiGUI(ttk.Frame):
    """Vendor API component lookup tab — embeddable in a notebook."""

    POLL_INTERVAL_MS = 100

    _COL_IDS = ("source", "mpn", "manufacturer", "description", "weight", "datasheet")
    _COL_HEADINGS = ("Source", "MPN", "Manufacturer", "Description", "Weight (g)", "Datasheet URL")
    _COL_WIDTHS = (70, 120, 130, 220, 70, 200)

    def __init__(self, parent: tk.Widget, config: VendorApiConfig) -> None:
        super().__init__(parent)
        self._config = config
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._worker_thread: Thread | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # --- Search section ---
        search_frame = ttk.LabelFrame(self, text="Component Lookup", padding=8)
        search_frame.pack(fill="x", **pad)

        self._mpn_var = tk.StringVar()
        row0 = ttk.Frame(search_frame)
        row0.pack(fill="x", pady=(0, 4))
        ttk.Label(row0, text="MPN:").pack(side="left", padx=(0, 4))
        self._mpn_entry = ttk.Entry(row0, textvariable=self._mpn_var, width=40)
        self._mpn_entry.pack(side="left", padx=(0, 8))
        self._mpn_entry.bind("<Return>", lambda _e: self._on_search())
        self._search_btn = ttk.Button(row0, text="Search", command=self._on_search)
        self._search_btn.pack(side="left")

        row1 = ttk.Frame(search_frame)
        row1.pack(fill="x")
        self._nexar_var = tk.BooleanVar(value=True)
        self._digikey_var = tk.BooleanVar(value=True)
        self._pdf_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="Nexar", variable=self._nexar_var).pack(
            side="left", padx=(0, 12)
        )
        ttk.Checkbutton(row1, text="DigiKey", variable=self._digikey_var).pack(
            side="left", padx=(0, 12)
        )
        ttk.Checkbutton(row1, text="PDF Weight", variable=self._pdf_var).pack(side="left")

        # --- Results table ---
        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, **pad)

        self._tree = ttk.Treeview(
            table_frame,
            columns=self._COL_IDS,
            show="headings",
            height=8,
            selectmode="browse",
        )
        for col_id, heading, width in zip(self._COL_IDS, self._COL_HEADINGS, self._COL_WIDTHS):
            self._tree.heading(col_id, text=heading)
            self._tree.column(col_id, width=width, minwidth=40, stretch=(col_id == "description"))

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # --- Log area ---
        log_frame = ttk.LabelFrame(self, text="Log", padding=4)
        log_frame.pack(fill="x", **pad)

        self._log_text = tk.Text(
            log_frame,
            height=6,
            state="disabled",
            wrap="word",
            bg="#f5f5f5",
            fg="#000000",
            insertbackground="#000000",
            selectbackground="#000000",
            selectforeground="#ffffff",
            font=("Consolas", 9),
        )
        log_sb = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_sb.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        # --- Action bar ---
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **pad)

        ttk.Button(action_frame, text="Settings", command=self._on_settings).pack(side="left")
        ttk.Button(action_frame, text="Clear", command=self._on_clear).pack(side="right")

    def _append_log(self, message: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _process_queue(self) -> None:
        try:
            while True:
                msg = self._queue.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self._append_log(msg[1])
                elif kind == "result":
                    result = msg[1]
                    weight_str = (
                        f"{result.weight_grams:.4g}" if result.weight_grams is not None else ""
                    )
                    self._tree.insert(
                        "",
                        "end",
                        iid=f"{result.source}:{result.mpn}",
                        values=(
                            result.source,
                            result.mpn,
                            result.manufacturer,
                            result.description,
                            weight_str,
                            result.datasheet_url,
                        ),
                    )
                elif kind == "weight":
                    _mpn, weight_grams = msg[1], msg[2]
                    weight_str = f"{weight_grams:.4g}" if weight_grams is not None else ""
                    for iid in self._tree.get_children():
                        vals = list(self._tree.item(iid, "values"))
                        if vals[1] == _mpn:
                            vals[4] = weight_str
                            self._tree.item(iid, values=vals)
                elif kind == "error":
                    self._append_log(f"ERROR: {msg[1]}")
                elif kind == "done":
                    self._search_btn.configure(state="normal")
                    self._mpn_entry.configure(state="normal")
        except queue.Empty:
            pass
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def _on_search(self) -> None:
        mpn = self._mpn_var.get().strip()
        if not mpn:
            self._append_log("Enter an MPN to search.")
            return

        for iid in self._tree.get_children():
            self._tree.delete(iid)

        self._search_btn.configure(state="disabled")
        self._mpn_entry.configure(state="disabled")

        use_nexar = self._nexar_var.get()
        use_digikey = self._digikey_var.get()
        use_pdf = self._pdf_var.get()

        self._worker_thread = Thread(
            target=self._search_worker,
            args=(mpn, use_nexar, use_digikey, use_pdf),
            daemon=True,
        )
        self._worker_thread.start()

    def _search_worker(self, mpn: str, use_nexar: bool, use_digikey: bool, use_pdf: bool) -> None:
        from vendor_api_tool.datasheet import lookup_weight_from_datasheet
        from vendor_api_tool.digikey import DigiKeyClient
        from vendor_api_tool.nexar import NexarClient, NexarError

        cfg: VendorApiConfig = self._config
        datasheet_urls: list[tuple[str, str]] = []  # (mpn, url)

        try:
            self._queue.put(("log", f"Searching for MPN: {mpn}..."))

            if use_nexar:
                if cfg.nexar_client_id and cfg.nexar_client_secret:
                    try:
                        client = NexarClient(cfg.nexar_client_id, cfg.nexar_client_secret)
                        results = client.search_mpn(mpn)
                        client.close()
                        if results:
                            self._queue.put(("log", f"Nexar: found {len(results)} result(s)"))
                            for r in results:
                                self._queue.put(("result", r))
                                if r.datasheet_url:
                                    datasheet_urls.append((r.mpn, r.datasheet_url))
                        else:
                            self._queue.put(("log", "Nexar: no results"))
                    except NexarError as exc:
                        self._queue.put(("error", f"Nexar: {exc}"))
                else:
                    self._queue.put(("log", "Nexar: not configured (no credentials)"))

            if use_digikey:
                if cfg.digikey_client_id and cfg.digikey_client_secret:
                    try:
                        dk = DigiKeyClient(cfg.digikey_client_id, cfg.digikey_client_secret)
                        result = dk.search_mpn(mpn)
                        dk.close()
                        if result is not None:
                            self._queue.put(("log", "DigiKey: found 1 result"))
                            self._queue.put(("result", result))
                            if result.datasheet_url:
                                datasheet_urls.append((result.mpn, result.datasheet_url))
                        else:
                            self._queue.put(("log", "DigiKey: no results"))
                    except Exception as exc:
                        self._queue.put(("error", f"DigiKey: {exc}"))
                else:
                    self._queue.put(("log", "DigiKey: not configured (no credentials)"))

            if use_pdf and datasheet_urls:
                for result_mpn, url in datasheet_urls:
                    self._queue.put(("log", f"PDF: looking up weight from {url}"))
                    try:
                        weight = lookup_weight_from_datasheet(url)
                        if weight is not None:
                            self._queue.put(
                                ("log", f"PDF: weight = {weight:.4g} g ({result_mpn})")
                            )
                            self._queue.put(("weight", result_mpn, weight))
                        else:
                            self._queue.put(("log", f"PDF: no weight found ({result_mpn})"))
                    except Exception as exc:
                        self._queue.put(("error", f"PDF weight lookup: {exc}"))

        except Exception as exc:
            self._queue.put(("error", str(exc)))
        finally:
            self._queue.put(("done",))

    def _on_settings(self) -> None:
        _SettingsDialog(self.winfo_toplevel(), self._config)

    def _on_clear(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def start_polling(self) -> None:
        """Start the queue poller. Called by the shell after tab is placed."""
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def close(self) -> None:
        """Called by the shell on window close."""
        pass


class _SettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, config: VendorApiConfig) -> None:
        super().__init__(parent)
        self._config = config
        self.title("Vendor API Settings")
        self.resizable(False, False)
        self.grab_set()

        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        fields: list[tuple[str, tk.StringVar, bool]] = [
            ("Nexar Client ID:", tk.StringVar(value=config.nexar_client_id), False),
            ("Nexar Client Secret:", tk.StringVar(value=config.nexar_client_secret), True),
            ("DigiKey Client ID:", tk.StringVar(value=config.digikey_client_id), False),
            ("DigiKey Client Secret:", tk.StringVar(value=config.digikey_client_secret), True),
        ]

        self._vars: list[tuple[str, tk.StringVar]] = []
        attr_names = [
            "nexar_client_id",
            "nexar_client_secret",
            "digikey_client_id",
            "digikey_client_secret",
        ]

        for row_idx, (label, var, secret) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row_idx, column=0, sticky="w", **pad)
            show = "*" if secret else ""
            ttk.Entry(frame, textvariable=var, width=36, show=show).grid(
                row=row_idx, column=1, sticky="ew", **pad
            )
            self._vars.append((attr_names[row_idx], var))

        frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=(8, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left")

        self.transient(parent)
        self.wait_window()

    def _on_save(self) -> None:
        from vendor_api_tool.config import save_vendor_api_config

        for attr, var in self._vars:
            setattr(self._config, attr, var.get().strip())
        save_vendor_api_config(self._config)
        self.destroy()
