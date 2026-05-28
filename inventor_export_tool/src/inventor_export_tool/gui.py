"""Tkinter GUI for the Inventor Batch Export Tool."""

from __future__ import annotations

import logging
import os
import queue
import tkinter as tk
from dataclasses import replace
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

        self._prompt_folder_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            out_frame,
            text="Prompt for folder on every export",
            variable=self._prompt_folder_var,
            command=self._save_config,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # --- Naming preset ---
        naming_frame = ttk.LabelFrame(root, text="Naming", padding=8)
        naming_frame.pack(fill="x", **pad)

        ttk.Label(naming_frame, text="Preset:").grid(row=0, column=0, sticky="w")
        self._preset_var = tk.StringVar()
        self._preset_combo = ttk.Combobox(
            naming_frame, textvariable=self._preset_var, state="readonly", width=35
        )
        self._preset_combo.grid(row=0, column=1, sticky="ew", padx=(4, 8))
        self._preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)
        ttk.Button(naming_frame, text="Manage...", command=self._on_manage_presets).grid(
            row=0, column=2
        )
        naming_frame.columnconfigure(1, weight=1)

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

        self._export_btn = ttk.Button(btn_frame, text="Run Export", command=self._on_export)
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

        self._preview_btn = ttk.Button(btn_frame, text="Preview", command=self._on_preview)
        self._preview_btn.pack(side="right", padx=(0, 8))

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
        self._refresh_preset_combo()
        self._preset_var.set(c.active_preset_name)
        self._prompt_folder_var.set(c.prompt_folder_on_export)

    def _save_config(self) -> None:
        self._config.output_folder = self._output_var.get()
        self._config.export_step = self._step_var.get()
        self._config.export_dwg = self._dwg_var.get()
        self._config.export_pdf = self._pdf_var.get()
        self._config.include_parts = self._parts_var.get()
        self._config.include_subassemblies = self._subasm_var.get()
        self._config.include_top_level = self._toplevel_var.get()
        self._config.include_suppressed = self._suppressed_var.get()
        self._config.active_preset_name = self._preset_var.get()
        self._config.prompt_folder_on_export = self._prompt_folder_var.get()

    def _get_current_config(self) -> AppConfig:
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
            naming_presets=self._config.naming_presets,
            active_preset_name=self._preset_var.get(),
            prompt_folder_on_export=self._prompt_folder_var.get(),
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
                elif msg_type == "preview_done":
                    self._on_worker_done()
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
        self._preview_btn.configure(state=state)
        self._export_btn.configure(state=state)
        self._cancel_btn.configure(state="normal" if working else "disabled")

    def _on_worker_done(self) -> None:
        self._set_working(False)
        self._worker_thread = None

    def _refresh_preset_combo(self) -> None:
        names = [p.name for p in self._config.naming_presets]
        self._preset_combo.configure(values=names)
        if self._config.active_preset_name in names:
            self._preset_var.set(self._config.active_preset_name)
        elif names:
            self._preset_var.set(names[0])

    def _on_preset_selected(self, _event: object = None) -> None:
        self._config.active_preset_name = self._preset_var.get()
        from inventor_export_tool.config import save_config

        save_config(self._config)

    def _on_manage_presets(self) -> None:
        from inventor_export_tool.naming_dialog import NamingPresetDialog

        dialog = NamingPresetDialog(
            self.winfo_toplevel(),
            self._config.naming_presets,
            self._config.active_preset_name,
        )
        if dialog.result is not None:
            presets, active_name = dialog.result
            self._config.naming_presets = presets
            self._config.active_preset_name = active_name
            from inventor_export_tool.config import save_config

            save_config(self._config)
            self._refresh_preset_combo()

    def _resolve_output_folder(self) -> str | None:
        """Return the export folder, or None if the user cancelled the picker.

        - prompt_folder_on_export=True → always show picker.
        - Output folder field is empty → show picker.
        - Otherwise → return the current field value without prompting.
        """
        current = self._output_var.get().strip()
        prompt = self._prompt_folder_var.get() or not current
        if prompt:
            path = filedialog.askdirectory(
                title="Select Output Folder",
                initialdir=current if current else os.path.expanduser("~"),
            )
            return path if path else None
        return current

    def _on_export(self) -> None:
        folder = self._resolve_output_folder()
        if folder is None:
            return
        self._output_var.set(folder)
        self._save_config()
        self._set_working(True)
        self._cancel_event.clear()
        self._progress_var.set(0)
        self._progress_label.configure(text="Exporting...")
        config = self._get_current_config()
        self._worker_thread = Thread(
            target=self._export_worker, args=(config, folder), daemon=True
        )
        self._worker_thread.start()

    def _export_worker(self, config: AppConfig, output_folder: str) -> None:
        from inventor_api._com_threading import com_thread_scope
        from inventor_export_tool.orchestrator import ExportOrchestrator

        try:
            with com_thread_scope():
                config = replace(config, output_folder=output_folder)
                orch = ExportOrchestrator(
                    config=config,
                    progress_callback=self.set_progress,
                    log_callback=self.log,
                )
                summary = orch.scan(output_folder=output_folder)
                orch.export(summary, self._cancel_event)
                self._queue.put(("export_done", orch.last_log_path))
        except Exception as e:
            logging.getLogger(__name__).exception("Worker thread failed")
            self._queue.put(("error", str(e)))

    def _on_preview(self) -> None:
        folder = self._resolve_output_folder()
        if folder is None:
            return
        self._output_var.set(folder)
        self._save_config()
        self._set_working(True)
        self._cancel_event.clear()
        self._progress_var.set(0)
        self._progress_label.configure(text="Scanning...")
        config = self._get_current_config()
        self._worker_thread = Thread(
            target=self._preview_worker, args=(config, folder), daemon=True
        )
        self._worker_thread.start()

    def _preview_worker(self, config: AppConfig, output_folder: str) -> None:
        from inventor_api._com_threading import com_thread_scope
        from inventor_export_tool.orchestrator import ExportOrchestrator

        try:
            with com_thread_scope():
                orch = ExportOrchestrator(
                    config=config,
                    progress_callback=self.set_progress,
                    log_callback=self.log,
                )
                summary = orch.scan(output_folder=output_folder)
                self._queue.put(("preview_done", summary))
        except Exception as e:
            logging.getLogger(__name__).exception("Worker thread failed")
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
