"""PDF Diff tab — compare two PDF files and produce an anaglyph diff PDF."""

from __future__ import annotations

import logging
import os
import queue
import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf_diff_tool.config import PdfDiffConfig

logger = logging.getLogger(__name__)


class PdfDiffGUI(ttk.Frame):
    """PDF visual diff tab content."""

    POLL_INTERVAL_MS = 100

    def __init__(self, parent: tk.Widget, config: PdfDiffConfig | None = None) -> None:
        super().__init__(parent)
        from pdf_diff_tool.config import PdfDiffConfig as _C

        self._config = config or _C()
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker_thread: Thread | None = None

        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # --- File selection ---
        file_frame = ttk.LabelFrame(self, text="PDF Files", padding=8)
        file_frame.pack(fill="x", **pad)
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="Old PDF:").grid(row=0, column=0, sticky="w", pady=2)
        self._old_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self._old_path_var, width=60).grid(
            row=0, column=1, sticky="ew", padx=(4, 4), pady=2
        )
        ttk.Button(file_frame, text="Browse...", command=self._browse_old).grid(
            row=0, column=2, pady=2
        )

        ttk.Label(file_frame, text="New PDF:").grid(row=1, column=0, sticky="w", pady=2)
        self._new_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self._new_path_var, width=60).grid(
            row=1, column=1, sticky="ew", padx=(4, 4), pady=2
        )
        ttk.Button(file_frame, text="Browse...", command=self._browse_new).grid(
            row=1, column=2, pady=2
        )

        # --- Settings ---
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill="x", **pad)

        ttk.Label(settings_frame, text="DPI:").pack(side="left")
        self._dpi_var = tk.IntVar(value=150)
        dpi_spin = ttk.Spinbox(
            settings_frame, from_=72, to=600, textvariable=self._dpi_var, width=6
        )
        dpi_spin.pack(side="left", padx=(4, 16))

        self._open_after_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, text="Open after comparison", variable=self._open_after_var
        ).pack(side="left")

        # --- Action button ---
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", **pad)

        self._compare_btn = ttk.Button(btn_frame, text="Compare", command=self._on_compare)
        self._compare_btn.pack(side="left")

        # --- Log area ---
        log_frame = ttk.LabelFrame(self, text="Log", padding=4)
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
        prog_frame = ttk.Frame(self)
        prog_frame.pack(fill="x", **pad)

        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(
            prog_frame, variable=self._progress_var, maximum=100
        )
        self._progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._progress_label = ttk.Label(prog_frame, text="Ready")
        self._progress_label.pack(side="right")

    # ------------------------------------------------------------------
    # File browsing
    # ------------------------------------------------------------------

    def _browse_old(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Old PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if path:
            self._old_path_var.set(path)

    def _browse_new(self) -> None:
        path = filedialog.askopenfilename(
            title="Select New PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if path:
            self._new_path_var.set(path)

    # ------------------------------------------------------------------
    # Config load / save
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        self._old_path_var.set(self._config.last_old_path)
        self._new_path_var.set(self._config.last_new_path)
        self._dpi_var.set(self._config.dpi)
        self._open_after_var.set(self._config.open_after_diff)

    def _save_config(self) -> None:
        self._config.last_old_path = self._old_path_var.get()
        self._config.last_new_path = self._new_path_var.get()
        self._config.dpi = self._dpi_var.get()
        self._config.open_after_diff = self._open_after_var.get()

    # ------------------------------------------------------------------
    # Queue-based thread communication
    # ------------------------------------------------------------------

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
                elif msg_type == "done":
                    result = data
                    if result.has_differences:
                        self._append_log(f"Differences found. Saved: {result.output_path.name}")
                    else:
                        self._append_log(
                            f"No differences found. Saved: {result.output_path.name}"
                        )
                    self._on_worker_done()
                    if self._open_after_var.get():
                        os.startfile(str(result.output_path))
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
        self._compare_btn.configure(state="disabled" if working else "normal")

    def _on_worker_done(self) -> None:
        self._set_working(False)
        self._worker_thread = None

    def _on_compare(self) -> None:
        old_path = self._old_path_var.get().strip()
        new_path = self._new_path_var.get().strip()

        if not old_path or not new_path:
            self._append_log("Please select both old and new PDF files.")
            return
        if not Path(old_path).exists():
            self._append_log(f"Old PDF not found: {old_path}")
            return
        if not Path(new_path).exists():
            self._append_log(f"New PDF not found: {new_path}")
            return

        self._save_config()
        self._set_working(True)
        self._progress_var.set(0)
        self._progress_label.configure(text="Starting...")

        self._worker_thread = Thread(
            target=self._run_worker, args=(old_path, new_path), daemon=True
        )
        self._worker_thread.start()

    def _run_worker(self, old_path: str, new_path: str) -> None:
        from pdf_diff_tool.differ import diff_pdfs

        old = Path(old_path)
        new = Path(new_path)
        output = new.parent / f"{old.stem}_vs_{new.stem}_diff.pdf"

        def progress_cb(current: int, total: int) -> None:
            self._queue.put(("progress", (current, total)))

        def log_cb(msg: str) -> None:
            self._queue.put(("log", msg))

        try:
            log_cb(f"Comparing: {old.name} vs {new.name}")
            result = diff_pdfs(old, new, output, dpi=self._config.dpi, progress_callback=progress_cb)
            self._queue.put(("done", result))
        except Exception as e:
            logger.exception("Diff worker failed")
            self._queue.put(("error", str(e)))

    # ------------------------------------------------------------------
    # Shell interface
    # ------------------------------------------------------------------

    def start_polling(self) -> None:
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def close(self) -> None:
        self._save_config()
