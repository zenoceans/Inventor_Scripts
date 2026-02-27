"""Tkinter GUI for the Inventor Drawing Release Tool."""

from __future__ import annotations

import logging
import os
import queue
import tkinter as tk
from threading import Event, Thread
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inventor_drawing_tool.config import DrawingConfig
    from inventor_drawing_tool.models import DrawingItem, ReleaseSummary, RevisionData, ScanResult


class DrawingToolGUI(ttk.Frame):
    """Drawing Release tab content — embeddable in a notebook."""

    POLL_INTERVAL_MS = 100

    def __init__(self, parent: tk.Widget, config: "DrawingConfig") -> None:
        super().__init__(parent)
        self._config = config
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancel_event = Event()
        self._worker_thread: Thread | None = None
        self._scan_result: ScanResult | None = None
        self._orchestrator = None
        self._last_log_path: str | None = None
        # Maps treeview item ID -> DrawingItem
        self._tree_items: dict[str, DrawingItem] = {}

        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = self
        pad = {"padx": 8, "pady": 4}

        # --- Drawing Template section ---
        tmpl_frame = ttk.LabelFrame(root, text="Drawing Template", padding=8)
        tmpl_frame.pack(fill="x", **pad)

        self._template_var = tk.StringVar()
        ttk.Label(tmpl_frame, text="Template (.idw):").grid(row=0, column=0, sticky="w")
        self._template_entry = ttk.Entry(tmpl_frame, textvariable=self._template_var, width=50)
        self._template_entry.grid(row=0, column=1, sticky="ew", padx=(4, 4))
        ttk.Button(tmpl_frame, text="Browse...", command=self._browse_template).grid(
            row=0, column=2
        )
        tmpl_frame.columnconfigure(1, weight=1)

        # --- Revision Data section ---
        rev_frame = ttk.LabelFrame(root, text="Revision Data", padding=8)
        rev_frame.pack(fill="x", **pad)

        self._rev_number_var = tk.StringVar()
        self._rev_description_var = tk.StringVar()
        self._made_by_var = tk.StringVar()
        self._approved_by_var = tk.StringVar()

        ttk.Label(rev_frame, text="Rev Number:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        ttk.Entry(rev_frame, textvariable=self._rev_number_var, width=10).grid(
            row=0, column=1, sticky="w", padx=(0, 16)
        )
        ttk.Label(rev_frame, text="Description:").grid(row=0, column=2, sticky="w", padx=(0, 4))
        ttk.Entry(rev_frame, textvariable=self._rev_description_var, width=35).grid(
            row=0, column=3, sticky="ew"
        )

        ttk.Label(rev_frame, text="Made By:").grid(
            row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0)
        )
        ttk.Entry(rev_frame, textvariable=self._made_by_var, width=20).grid(
            row=1, column=1, sticky="ew", padx=(0, 16), pady=(4, 0)
        )
        ttk.Label(rev_frame, text="Approved By:").grid(
            row=1, column=2, sticky="w", padx=(0, 4), pady=(4, 0)
        )
        ttk.Entry(rev_frame, textvariable=self._approved_by_var, width=20).grid(
            row=1, column=3, sticky="ew", pady=(4, 0)
        )

        rev_frame.columnconfigure(3, weight=1)

        # --- Review Table section ---
        tree_frame = ttk.LabelFrame(root, text="Review Table", padding=8)
        tree_frame.pack(fill="both", expand=True, **pad)

        columns = ("include", "part_name", "doc_type", "status", "drawing_path")
        self._tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=8,
            selectmode="extended",
        )
        self._tree.heading("include", text="Include")
        self._tree.heading("part_name", text="Part Name")
        self._tree.heading("doc_type", text="Type")
        self._tree.heading("status", text="Status")
        self._tree.heading("drawing_path", text="Drawing Path")

        self._tree.column("include", width=60, minwidth=50, anchor="center")
        self._tree.column("part_name", width=180, minwidth=80)
        self._tree.column("doc_type", width=80, minwidth=60, anchor="center")
        self._tree.column("status", width=100, minwidth=70, anchor="center")
        self._tree.column("drawing_path", width=300, minwidth=100)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self._tree.bind("<Button-1>", self._on_tree_click)

        # Select All / Deselect All buttons
        sel_btn_frame = ttk.Frame(root)
        sel_btn_frame.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(sel_btn_frame, text="Select All", command=self._select_all).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(sel_btn_frame, text="Deselect All", command=self._deselect_all).pack(
            side="left"
        )

        # --- Action Buttons section ---
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", **pad)

        self._scan_btn = ttk.Button(btn_frame, text="Scan Assembly", command=self._on_scan)
        self._scan_btn.pack(side="left", padx=(0, 8))

        self._execute_btn = ttk.Button(
            btn_frame, text="Execute Release", command=self._on_execute, state="disabled"
        )
        self._execute_btn.pack(side="left", padx=(0, 8))

        self._cancel_btn = ttk.Button(
            btn_frame, text="Cancel", command=self._on_cancel, state="disabled"
        )
        self._cancel_btn.pack(side="left")

        self._settings_btn = ttk.Button(btn_frame, text="Settings...", command=self._on_settings)
        self._settings_btn.pack(side="right")

        self._open_log_btn = ttk.Button(
            btn_frame, text="Open Log", command=self._on_open_log, state="disabled"
        )
        self._open_log_btn.pack(side="right", padx=(0, 8))

        # --- Log section ---
        log_frame = ttk.LabelFrame(root, text="Log", padding=4)
        log_frame.pack(fill="both", expand=True, **pad)

        self._log_text = tk.Text(
            log_frame,
            height=8,
            state="disabled",
            wrap="word",
            bg="#f5f5f5",
            fg="#000000",
            insertbackground="#000000",
            selectbackground="#000000",
            selectforeground="#ffffff",
            font=("Consolas", 9),
        )
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        # --- Progress section ---
        prog_frame = ttk.Frame(root)
        prog_frame.pack(fill="x", **pad)

        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(prog_frame, variable=self._progress_var, maximum=100)
        self._progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._progress_label = ttk.Label(prog_frame, text="Ready")
        self._progress_label.pack(side="right")

    # ------------------------------------------------------------------
    # Config load / save
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        c = self._config
        self._template_var.set(c.template_path)
        self._rev_number_var.set(c.last_rev_number)
        self._rev_description_var.set(c.last_rev_description)
        self._made_by_var.set(c.last_made_by)
        self._approved_by_var.set(c.last_approved_by)

    def _save_config(self) -> None:
        self._config.template_path = self._template_var.get()
        self._config.last_rev_number = self._rev_number_var.get()
        self._config.last_rev_description = self._rev_description_var.get()
        self._config.last_made_by = self._made_by_var.get()
        self._config.last_approved_by = self._approved_by_var.get()

    # ------------------------------------------------------------------
    # Browse handlers
    # ------------------------------------------------------------------

    def _browse_template(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Drawing Template",
            filetypes=[
                ("Inventor Drawing Template", "*.idw *.dwt"),
                ("All Files", "*.*"),
            ],
        )
        if path:
            self._template_var.set(path)

    # ------------------------------------------------------------------
    # Treeview helpers
    # ------------------------------------------------------------------

    def _populate_tree(self, scan_result: "ScanResult") -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._tree_items.clear()

        for item in scan_result.items:
            check = "\u2611" if item.include_in_release else "\u2610"
            drawing_path = item.drawing_path or ""
            iid = self._tree.insert(
                "",
                "end",
                values=(
                    check,
                    item.part_name,
                    item.document_type,
                    item.drawing_status.value,
                    drawing_path,
                ),
            )
            self._tree_items[iid] = item

    def _on_tree_click(self, event: tk.Event) -> None:
        region = self._tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self._tree.identify_column(event.x)
        if col != "#1":
            return
        iid = self._tree.identify_row(event.y)
        if not iid or iid not in self._tree_items:
            return
        di = self._tree_items[iid]
        di.include_in_release = not di.include_in_release
        check = "\u2611" if di.include_in_release else "\u2610"
        vals = list(self._tree.item(iid, "values"))
        vals[0] = check
        self._tree.item(iid, values=vals)

    def _select_all(self) -> None:
        for iid, di in self._tree_items.items():
            di.include_in_release = True
            vals = list(self._tree.item(iid, "values"))
            vals[0] = "\u2611"
            self._tree.item(iid, values=vals)

    def _deselect_all(self) -> None:
        for iid, di in self._tree_items.items():
            di.include_in_release = False
            vals = list(self._tree.item(iid, "values"))
            vals[0] = "\u2610"
            self._tree.item(iid, values=vals)

    def _get_items_from_treeview(self) -> list["DrawingItem"]:
        return list(self._tree_items.values())

    # ------------------------------------------------------------------
    # Revision data helper
    # ------------------------------------------------------------------

    def _get_revision_data(self) -> RevisionData:
        from inventor_drawing_tool.models import RevisionData

        return RevisionData(
            rev_number=self._rev_number_var.get().strip(),
            rev_description=self._rev_description_var.get().strip(),
            made_by=self._made_by_var.get().strip(),
            approved_by=self._approved_by_var.get().strip(),
        )

    # ------------------------------------------------------------------
    # Queue-based thread communication
    # ------------------------------------------------------------------

    def log(self, message: str) -> None:
        """Append a message to the log area (thread-safe via queue)."""
        self._queue.put(("log", message))

    def set_progress(self, current: int, total: int) -> None:
        """Update progress bar (thread-safe via queue)."""
        self._queue.put(("progress", (current, total)))

    def _process_queue(self) -> None:
        try:
            while True:
                msg_type, data = self._queue.get_nowait()
                if msg_type == "log":
                    self._append_log(data)
                elif msg_type == "progress":
                    current, total = data
                    if total > 0:
                        pct = (current / total) * 100
                        self._progress_var.set(pct)
                        self._progress_label.configure(text=f"{current}/{total} ({pct:.0f}%)")
                    else:
                        self._progress_var.set(0)
                        self._progress_label.configure(text="Ready")
                elif msg_type == "scan_done":
                    self._scan_result = data
                    self._populate_tree(data)
                    self._on_worker_done()
                    self._execute_btn.configure(state="normal")
                    self._append_log(f"Scan complete: {data.total_parts} component(s) found.")
                elif msg_type == "execute_done":
                    summary: ReleaseSummary = data
                    if self._orchestrator is not None and self._orchestrator.last_log_path:
                        self._last_log_path = str(self._orchestrator.last_log_path)
                        self._open_log_btn.configure(state="normal")
                    self._on_worker_done()
                    self._append_log(
                        f"Release complete: {summary.created} created, "
                        f"{summary.revised} revised, {summary.failed} failed."
                    )
                    self._save_config()
                elif msg_type == "error":
                    self._append_log(f"ERROR: {data}")
                    self._on_worker_done()
        except queue.Empty:
            pass
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def _append_log(self, message: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Button state management
    # ------------------------------------------------------------------

    def _set_working(self, working: bool) -> None:
        state = "disabled" if working else "normal"
        self._scan_btn.configure(state=state)
        self._settings_btn.configure(state=state)
        self._cancel_btn.configure(state="normal" if working else "disabled")
        if working:
            self._execute_btn.configure(state="disabled")

    def _on_worker_done(self) -> None:
        self._set_working(False)
        self._worker_thread = None

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _on_scan(self) -> None:
        self._scan_result = None
        self._orchestrator = None
        self._execute_btn.configure(state="disabled")
        self._open_log_btn.configure(state="disabled")
        self._last_log_path = None

        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._tree_items.clear()

        self._set_working(True)
        self._cancel_event.clear()
        self._progress_var.set(0)
        self._progress_label.configure(text="Scanning...")

        self._worker_thread = Thread(target=self._scan_worker, daemon=True)
        self._worker_thread.start()

    def _scan_worker(self) -> None:
        from inventor_api._com_threading import com_thread_scope
        from inventor_drawing_tool.orchestrator import DrawingReleaseOrchestrator

        try:
            with com_thread_scope():
                revision_data = self._get_revision_data()
                self._orchestrator = DrawingReleaseOrchestrator(
                    self._config,
                    revision_data,
                    progress_callback=self.set_progress,
                    log_callback=self.log,
                )
                result = self._orchestrator.scan()
                self._queue.put(("scan_done", result))
        except Exception as e:
            logging.getLogger(__name__).exception("Worker thread failed")
            self._queue.put(("error", str(e)))

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _on_execute(self) -> None:
        if self._scan_result is None:
            self._append_log("Run scan first.")
            return

        self._set_working(True)
        self._cancel_event.clear()
        self._progress_var.set(0)
        self._progress_label.configure(text="Releasing...")

        items = self._get_items_from_treeview()
        self._worker_thread = Thread(target=self._execute_worker, args=(items,), daemon=True)
        self._worker_thread.start()

    def _execute_worker(self, items: list["DrawingItem"]) -> None:
        from inventor_api._com_threading import com_thread_scope
        from inventor_drawing_tool.orchestrator import DrawingReleaseOrchestrator

        try:
            with com_thread_scope():
                revision_data = self._get_revision_data()
                self._orchestrator = DrawingReleaseOrchestrator(
                    self._config,
                    revision_data,
                    progress_callback=self.set_progress,
                    log_callback=self.log,
                )
                summary = self._orchestrator.execute(items, self._cancel_event)
                self._queue.put(("execute_done", summary))
        except Exception as e:
            logging.getLogger(__name__).exception("Worker thread failed")
            self._queue.put(("error", str(e)))

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def _on_cancel(self) -> None:
        self._cancel_event.set()
        self._append_log("Cancelling...")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _on_settings(self) -> None:
        from inventor_drawing_tool.settings_dialog import DrawingSettingsDialog

        dialog = DrawingSettingsDialog(self.winfo_toplevel(), self._config)
        self.wait_window(dialog)
        if dialog.result is not None:
            self._config = dialog.result
            from inventor_drawing_tool.config import save_drawing_config

            save_drawing_config(self._config)

    # ------------------------------------------------------------------
    # Open Log
    # ------------------------------------------------------------------

    def _on_open_log(self) -> None:
        if self._last_log_path:
            os.startfile(self._last_log_path)

    # ------------------------------------------------------------------
    # Shell interface
    # ------------------------------------------------------------------

    def start_polling(self) -> None:
        """Start the queue poller. Called by the shell after tab is placed."""
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def close(self) -> None:
        """Called by the shell on window close."""
        self._save_config()
        if self._worker_thread and self._worker_thread.is_alive():
            self._cancel_event.set()
