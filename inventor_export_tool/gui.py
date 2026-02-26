"""Tkinter GUI for the Inventor Batch Export Tool."""

from __future__ import annotations

import os
import queue
import tkinter as tk
from threading import Event, Thread
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inventor_export_tool.config import AppConfig


class ExportToolGUI(ttk.Frame):
    """Inventor Export tab content — embeddable in a notebook."""

    POLL_INTERVAL_MS = 100

    def __init__(self, parent: tk.Widget, config: AppConfig) -> None:
        super().__init__(parent)
        self._config = config
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancel_event = Event()
        self._worker_thread: Thread | None = None
        self._last_log_path: str | None = None

        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        root = self
        pad = {"padx": 8, "pady": 4}

        # --- Assembly section ---
        asm_frame = ttk.LabelFrame(root, text="Assembly", padding=8)
        asm_frame.pack(fill="x", **pad)

        self._asm_path_var = tk.StringVar()
        ttk.Label(asm_frame, text="File:").grid(row=0, column=0, sticky="w")
        self._asm_entry = ttk.Entry(asm_frame, textvariable=self._asm_path_var, width=50)
        self._asm_entry.grid(row=0, column=1, sticky="ew", padx=(4, 4))
        ttk.Button(asm_frame, text="Browse...", command=self._browse_assembly).grid(
            row=0, column=2
        )

        self._use_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            asm_frame,
            text="Use active document in Inventor",
            variable=self._use_active_var,
            command=self._toggle_assembly_entry,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        asm_frame.columnconfigure(1, weight=1)
        self._toggle_assembly_entry()

        # --- Output section ---
        out_frame = ttk.LabelFrame(root, text="Output Folder", padding=8)
        out_frame.pack(fill="x", **pad)

        self._output_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self._output_var, width=50).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(out_frame, text="Browse...", command=self._browse_output).grid(row=0, column=1)
        out_frame.columnconfigure(0, weight=1)

        # --- Export options ---
        opt_frame = ttk.LabelFrame(root, text="Export Options", padding=8)
        opt_frame.pack(fill="x", **pad)

        self._step_var = tk.BooleanVar(value=True)
        self._dwg_var = tk.BooleanVar(value=True)
        self._pdf_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="STEP (.step)", variable=self._step_var).grid(
            row=0, column=0, sticky="w", padx=(0, 16)
        )
        ttk.Checkbutton(opt_frame, text="DWG (.dwg)", variable=self._dwg_var).grid(
            row=0, column=1, sticky="w", padx=(0, 16)
        )
        ttk.Checkbutton(opt_frame, text="PDF (.pdf)", variable=self._pdf_var).grid(
            row=0, column=2, sticky="w"
        )

        # --- Include options ---
        inc_frame = ttk.LabelFrame(root, text="Include", padding=8)
        inc_frame.pack(fill="x", **pad)

        self._parts_var = tk.BooleanVar(value=True)
        self._subasm_var = tk.BooleanVar(value=True)
        self._toplevel_var = tk.BooleanVar(value=True)
        self._suppressed_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(inc_frame, text="Parts (IPT)", variable=self._parts_var).grid(
            row=0, column=0, sticky="w", padx=(0, 16)
        )
        ttk.Checkbutton(inc_frame, text="Sub-assemblies (IAM)", variable=self._subasm_var).grid(
            row=0, column=1, sticky="w", padx=(0, 16)
        )
        ttk.Checkbutton(inc_frame, text="Top-level assembly", variable=self._toplevel_var).grid(
            row=0, column=2, sticky="w"
        )
        ttk.Checkbutton(
            inc_frame, text="Suppressed components", variable=self._suppressed_var
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # --- Action buttons ---
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", **pad)

        self._scan_btn = ttk.Button(btn_frame, text="Scan Assembly", command=self._on_scan)
        self._scan_btn.pack(side="left", padx=(0, 8))

        self._export_btn = ttk.Button(
            btn_frame, text="Run Export", command=self._on_export, state="disabled"
        )
        self._export_btn.pack(side="left", padx=(0, 8))

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

        # --- Log area ---
        log_frame = ttk.LabelFrame(root, text="Log", padding=4)
        log_frame.pack(fill="both", expand=True, **pad)

        self._log_text = tk.Text(
            log_frame,
            height=12,
            state="disabled",
            wrap="word",
            bg="#f5f5f5",
            fg="#000000",
            insertbackground="#000000",
            selectbackground="#000000",
            selectforeground="#ffffff",
            font=("Consolas", 9),
        )
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Progress bar ---
        prog_frame = ttk.Frame(root)
        prog_frame.pack(fill="x", **pad)

        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(prog_frame, variable=self._progress_var, maximum=100)
        self._progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._progress_label = ttk.Label(prog_frame, text="Ready")
        self._progress_label.pack(side="right")

        # Internal state
        self._scan_summary = None

    def _toggle_assembly_entry(self) -> None:
        state = "disabled" if self._use_active_var.get() else "normal"
        self._asm_entry.configure(state=state)

    def _browse_assembly(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Assembly",
            filetypes=[("Inventor Assembly", "*.iam"), ("All Files", "*.*")],
        )
        if path:
            self._asm_path_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self._output_var.set(path)

    def _load_config(self) -> None:
        c = self._config
        self._output_var.set(c.output_folder)
        self._step_var.set(c.export_step)
        self._dwg_var.set(c.export_dwg)
        self._pdf_var.set(c.export_pdf)
        self._parts_var.set(c.include_parts)
        self._subasm_var.set(c.include_subassemblies)
        self._toplevel_var.set(c.include_top_level)
        self._suppressed_var.set(c.include_suppressed)

    def _save_config(self) -> None:
        self._config.output_folder = self._output_var.get()
        self._config.export_step = self._step_var.get()
        self._config.export_dwg = self._dwg_var.get()
        self._config.export_pdf = self._pdf_var.get()
        self._config.include_parts = self._parts_var.get()
        self._config.include_subassemblies = self._subasm_var.get()
        self._config.include_top_level = self._toplevel_var.get()
        self._config.include_suppressed = self._suppressed_var.get()

    def _get_current_config(self) -> AppConfig:
        """Return a fresh AppConfig from current GUI state."""
        from inventor_export_tool.config import AppConfig

        return AppConfig(
            output_folder=self._output_var.get(),
            export_step=self._step_var.get(),
            export_dwg=self._dwg_var.get(),
            export_pdf=self._pdf_var.get(),
            include_parts=self._parts_var.get(),
            include_subassemblies=self._subasm_var.get(),
            include_top_level=self._toplevel_var.get(),
            include_suppressed=self._suppressed_var.get(),
            export_options=self._config.export_options,
        )

    def log(self, message: str) -> None:
        """Append a message to the log area (thread-safe via queue)."""
        self._queue.put(("log", message))

    def set_progress(self, current: int, total: int) -> None:
        """Update progress bar (thread-safe via queue)."""
        self._queue.put(("progress", (current, total)))

    def _process_queue(self) -> None:
        """Process pending messages from the worker thread."""
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
                    self._scan_summary = data
                    self._on_worker_done()
                    self._export_btn.configure(state="normal")
                elif msg_type == "export_done":
                    if data is not None:
                        self._last_log_path = str(data)
                        self._open_log_btn.configure(state="normal")
                    self._on_worker_done()
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

    def _set_working(self, working: bool) -> None:
        state = "disabled" if working else "normal"
        self._scan_btn.configure(state=state)
        self._cancel_btn.configure(state="normal" if working else "disabled")
        if working:
            self._export_btn.configure(state="disabled")

    def _on_worker_done(self) -> None:
        self._set_working(False)
        self._worker_thread = None

    def _on_scan(self) -> None:
        if not self._output_var.get():
            self._append_log("Please select an output folder first.")
            return

        self._scan_summary = None
        self._export_btn.configure(state="disabled")
        self._set_working(True)
        self._cancel_event.clear()
        self._progress_var.set(0)
        self._progress_label.configure(text="Scanning...")

        config = self._get_current_config()
        self._worker_thread = Thread(target=self._scan_worker, args=(config,), daemon=True)
        self._worker_thread.start()

    def _scan_worker(self, config: AppConfig) -> None:
        from inventor_api._com_threading import com_thread_scope
        from inventor_export_tool.orchestrator import ExportOrchestrator

        try:
            with com_thread_scope():
                orch = ExportOrchestrator(
                    config=config,
                    progress_callback=self.set_progress,
                    log_callback=self.log,
                )
                summary = orch.scan()
                self._queue.put(("scan_done", (summary, orch)))
        except Exception as e:
            self._queue.put(("error", str(e)))

    def _on_export(self) -> None:
        if self._scan_summary is None:
            self._append_log("Run scan first.")
            return

        summary, orch = self._scan_summary
        self._set_working(True)
        self._cancel_event.clear()
        self._progress_var.set(0)
        self._progress_label.configure(text="Exporting...")

        self._worker_thread = Thread(target=self._export_worker, args=(orch, summary), daemon=True)
        self._worker_thread.start()

    def _export_worker(self, orch, summary) -> None:
        from inventor_api._com_threading import com_thread_scope

        try:
            # Note: orch already has a COM connection from scan.
            # But since we're on a new thread, we need a new COM scope.
            # Actually, scan and export should share the same COM thread.
            # Let's restructure: scan_worker stores the orch, and export_worker
            # creates a new COM scope and reconnects.
            with com_thread_scope():
                from inventor_export_tool.orchestrator import ExportOrchestrator

                # Reconnect since we're on a new thread
                config = self._get_current_config()
                orch = ExportOrchestrator(
                    config=config,
                    progress_callback=self.set_progress,
                    log_callback=self.log,
                )
                # Re-scan quickly (we need the COM connection)
                new_summary = orch.scan()
                orch.export(new_summary, self._cancel_event)
                self._queue.put(("export_done", orch.last_log_path))
        except Exception as e:
            self._queue.put(("error", str(e)))

    def _on_cancel(self) -> None:
        self._cancel_event.set()
        self._append_log("Cancelling...")

    def start_polling(self) -> None:
        """Start the queue poller. Called by the shell after tab is placed."""
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def _on_settings(self) -> None:
        from inventor_export_tool.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.winfo_toplevel(), self._config.export_options)
        if dialog.result is not None:
            self._config.export_options = dialog.result
            from inventor_export_tool.config import save_config

            save_config(self._config)

    def _on_open_log(self) -> None:
        if self._last_log_path:
            os.startfile(self._last_log_path)

    def close(self) -> None:
        """Called by the shell on window close."""
        self._save_config()
        if self._worker_thread and self._worker_thread.is_alive():
            self._cancel_event.set()
