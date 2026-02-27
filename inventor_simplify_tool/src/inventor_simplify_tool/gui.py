"""STEP Simplify tab — batch import STEP files, simplify, and export .ipt."""

from __future__ import annotations

import logging
import os
import queue
import tkinter as tk
from pathlib import Path
from threading import Event, Thread
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inventor_simplify_tool.config import SimplifyConfig
    from inventor_simplify_tool.models import SimplifyRow


class SimplifyToolGUI(ttk.Frame):
    """Batch STEP Import + Simplify tab content."""

    POLL_INTERVAL_MS = 100

    def __init__(self, parent: tk.Widget, config: SimplifyConfig | None = None) -> None:
        super().__init__(parent)
        from inventor_simplify_tool.config import SimplifyConfig as _SC

        self._config = config or _SC()
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancel_event = Event()
        self._worker_thread: Thread | None = None
        self._last_log_path: str | None = None

        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = self
        pad = {"padx": 8, "pady": 4}

        # --- Batch table ---
        table_frame = ttk.LabelFrame(root, text="STEP Files", padding=8)
        table_frame.pack(fill="both", expand=True, **pad)

        columns = ("step_path", "output_name", "output_folder")
        self._tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=8, selectmode="extended"
        )
        self._tree.heading("step_path", text="STEP File")
        self._tree.heading("output_name", text="Output Name")
        self._tree.heading("output_folder", text="Output Folder")
        self._tree.column("step_path", width=280, minwidth=120)
        self._tree.column("output_name", width=160, minwidth=80)
        self._tree.column("output_folder", width=220, minwidth=100)

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Double-click to edit the Output Name column
        self._tree.bind("<Double-1>", self._on_tree_double_click)
        self._edit_widget: tk.Entry | None = None

        # --- Table buttons ---
        tbl_btn_frame = ttk.Frame(root)
        tbl_btn_frame.pack(fill="x", **pad)

        ttk.Button(tbl_btn_frame, text="Add Files...", command=self._on_add_files).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(tbl_btn_frame, text="Remove Selected", command=self._on_remove_selected).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(
            tbl_btn_frame, text="Set Output Folder...", command=self._on_set_output_folder
        ).pack(side="left", padx=(0, 4))
        ttk.Button(tbl_btn_frame, text="Clear All", command=self._on_clear_all).pack(side="left")

        # --- Assembly target ---
        asm_frame = ttk.LabelFrame(root, text="Add to Assembly (optional)", padding=8)
        asm_frame.pack(fill="x", **pad)

        self._add_to_asm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            asm_frame,
            text="Insert simplified .ipt into target assembly",
            variable=self._add_to_asm_var,
            command=self._toggle_asm_entry,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(asm_frame, text="Assembly:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._asm_path_var = tk.StringVar()
        self._asm_entry = ttk.Entry(asm_frame, textvariable=self._asm_path_var, width=50)
        self._asm_entry.grid(row=1, column=1, sticky="ew", padx=(4, 4), pady=(4, 0))
        self._asm_browse_btn = ttk.Button(asm_frame, text="Browse...", command=self._browse_asm)
        self._asm_browse_btn.grid(row=1, column=2, pady=(4, 0))
        asm_frame.columnconfigure(1, weight=1)
        self._toggle_asm_entry()

        # --- Action buttons ---
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", **pad)

        self._run_btn = ttk.Button(btn_frame, text="Run Simplify", command=self._on_run)
        self._run_btn.pack(side="left", padx=(0, 8))

        self._cancel_btn = ttk.Button(
            btn_frame, text="Cancel", command=self._on_cancel, state="disabled"
        )
        self._cancel_btn.pack(side="left")

        self._open_log_btn = ttk.Button(
            btn_frame, text="Open Log", command=self._on_open_log, state="disabled"
        )
        self._open_log_btn.pack(side="right")

        # --- Log area ---
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

        # --- Progress bar ---
        prog_frame = ttk.Frame(root)
        prog_frame.pack(fill="x", **pad)

        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(prog_frame, variable=self._progress_var, maximum=100)
        self._progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._progress_label = ttk.Label(prog_frame, text="Ready")
        self._progress_label.pack(side="right")

    # ------------------------------------------------------------------
    # Table interactions
    # ------------------------------------------------------------------

    def _on_add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select STEP Files",
            filetypes=[("STEP Files", "*.stp *.step"), ("All Files", "*.*")],
        )
        for p in paths:
            name = Path(p).stem
            folder = str(Path(p).parent)
            self._tree.insert("", "end", values=(p, name, folder))

    def _on_remove_selected(self) -> None:
        for item in self._tree.selection():
            self._tree.delete(item)

    def _on_set_output_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Output Folder")
        if not folder:
            return
        selected = self._tree.selection()
        items = selected if selected else self._tree.get_children()
        for item in items:
            vals = list(self._tree.item(item, "values"))
            vals[2] = folder
            self._tree.item(item, values=vals)

    def _on_clear_all(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

    def _on_tree_double_click(self, event: tk.Event) -> None:
        """Open an inline Entry on the Output Name column when double-clicked."""
        region = self._tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self._tree.identify_column(event.x)
        if col != "#2":  # Only allow editing the Output Name column
            return
        item = self._tree.identify_row(event.y)
        if not item:
            return
        self._start_cell_edit(item)

    def _start_cell_edit(self, item: str) -> None:
        """Place an Entry widget over the Output Name cell for editing."""
        self._finish_cell_edit()  # close any previous edit

        bbox = self._tree.bbox(item, column="output_name")
        if not bbox:
            return
        x, y, w, h = bbox

        vals = list(self._tree.item(item, "values"))
        current_name = vals[1]

        entry = tk.Entry(self._tree, font=("Segoe UI", 10))
        entry.insert(0, current_name)
        entry.select_range(0, "end")
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()

        entry.bind("<Return>", lambda e: self._commit_cell_edit(item, entry))
        entry.bind("<Escape>", lambda e: self._finish_cell_edit())
        entry.bind("<FocusOut>", lambda e: self._commit_cell_edit(item, entry))

        self._edit_widget = entry

    def _commit_cell_edit(self, item: str, entry: tk.Entry) -> None:
        """Save the edited value back to the Treeview row."""
        new_name = entry.get().strip()
        if new_name:
            vals = list(self._tree.item(item, "values"))
            vals[1] = new_name
            self._tree.item(item, values=vals)
        self._finish_cell_edit()

    def _finish_cell_edit(self) -> None:
        """Remove the inline edit widget."""
        if self._edit_widget is not None:
            self._edit_widget.destroy()
            self._edit_widget = None

    # ------------------------------------------------------------------
    # Assembly target toggle
    # ------------------------------------------------------------------

    def _toggle_asm_entry(self) -> None:
        state = "normal" if self._add_to_asm_var.get() else "disabled"
        self._asm_entry.configure(state=state)
        self._asm_browse_btn.configure(state=state)

    def _browse_asm(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Target Assembly",
            filetypes=[("Inventor Assembly", "*.iam"), ("All Files", "*.*")],
        )
        if path:
            self._asm_path_var.set(path)

    # ------------------------------------------------------------------
    # Config load / save
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        self._add_to_asm_var.set(self._config.add_to_assembly)
        self._asm_path_var.set(self._config.target_assembly_path)
        self._toggle_asm_entry()

    def _save_config(self) -> None:
        self._config.add_to_assembly = self._add_to_asm_var.get()
        self._config.target_assembly_path = self._asm_path_var.get()

    # ------------------------------------------------------------------
    # Queue-based thread communication
    # ------------------------------------------------------------------

    def log(self, message: str) -> None:
        self._queue.put(("log", message))

    def set_progress(self, current: int, total: int) -> None:
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
                elif msg_type == "done":
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

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _set_working(self, working: bool) -> None:
        state = "disabled" if working else "normal"
        self._run_btn.configure(state=state)
        self._cancel_btn.configure(state="normal" if working else "disabled")

    def _on_worker_done(self) -> None:
        self._set_working(False)
        self._worker_thread = None

    def _on_run(self) -> None:
        rows = self._collect_rows()
        if not rows:
            self._append_log("Add at least one STEP file to the table.")
            return

        self._save_config()
        self._set_working(True)
        self._cancel_event.clear()
        self._progress_var.set(0)
        self._progress_label.configure(text="Starting...")

        self._worker_thread = Thread(target=self._run_worker, args=(rows,), daemon=True)
        self._worker_thread.start()

    def _collect_rows(self) -> list[SimplifyRow]:
        from inventor_simplify_tool.models import SimplifyRow

        rows: list[SimplifyRow] = []
        for item in self._tree.get_children():
            vals = self._tree.item(item, "values")
            rows.append(
                SimplifyRow(step_path=vals[0], output_filename=vals[1], output_folder=vals[2])
            )
        return rows

    def _run_worker(self, rows: list) -> None:
        from inventor_api._com_threading import com_thread_scope
        from inventor_simplify_tool.orchestrator import SimplifyOrchestrator

        try:
            with com_thread_scope():
                orch = SimplifyOrchestrator(
                    config=self._config,
                    rows=rows,
                    progress_callback=self.set_progress,
                    log_callback=self.log,
                )
                orch.run(cancel_event=self._cancel_event)
                self._queue.put(("done", orch.last_log_path))
        except Exception as e:
            logging.getLogger(__name__).exception("Worker thread failed")
            self._queue.put(("error", str(e)))

    def _on_cancel(self) -> None:
        self._cancel_event.set()
        self._append_log("Cancelling...")

    # ------------------------------------------------------------------
    # Shell interface
    # ------------------------------------------------------------------

    def start_polling(self) -> None:
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def close(self) -> None:
        self._save_config()
        if self._worker_thread and self._worker_thread.is_alive():
            self._cancel_event.set()

    def _on_open_log(self) -> None:
        if self._last_log_path:
            os.startfile(self._last_log_path)
