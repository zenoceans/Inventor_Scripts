"""Tkinter GUI for the Wattius BMU Commissioning Tool."""

from __future__ import annotations

import logging
import os
import queue
import tkinter as tk
from datetime import datetime
from threading import Event, Thread
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wattius_commissioning_tool.config import CommissioningConfig
    from wattius_commissioning_tool.models import BoardResult, CommissioningStep, SessionState

_STEP_LABELS = [
    ("CONNECTING", "Connect"),
    ("FLASHING", "Flash"),
    ("CONFIGURING", "Config"),
    ("APPLYING_SETUP", "Setup"),
    ("TESTING", "Test"),
    ("LOGGING", "Log"),
]

_CAN_BAUDRATES = [
    "CAN_125kbps",
    "CAN_250kbps",
    "CAN_500kbps",
    "CAN_1000kbps",
]

_BLE_MODES = ["DISABLED", "ENABLED"]

_NETWORK_MODES = ["DISABLE", "DHCP", "STATIC"]


class CommissioningToolGUI(ttk.Frame):
    """BMU Commissioning tab — embeddable in a Zabra-Cadabra notebook."""

    POLL_INTERVAL_MS = 100

    def __init__(self, parent: tk.Widget, config: "CommissioningConfig") -> None:
        super().__init__(parent)
        self._config = config
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._cancel_event = Event()
        self._worker_thread: Thread | None = None
        self._session: SessionState | None = None
        self._toolkit_manager = None
        self._logger = None
        self._step_labels: dict[str, ttk.Label] = {}

        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # --- Settings section ---
        settings_frame = ttk.LabelFrame(self, text="Settings", padding=8)
        settings_frame.pack(fill="x", **pad)

        # Row 0: Toolkit path
        self._toolkit_var = tk.StringVar()
        ttk.Label(settings_frame, text="Toolkit Path:").grid(
            row=0, column=0, sticky="w", padx=(0, 4)
        )
        ttk.Entry(settings_frame, textvariable=self._toolkit_var, width=52).grid(
            row=0, column=1, sticky="ew", padx=(0, 4)
        )
        ttk.Button(settings_frame, text="Browse...", command=self._browse_toolkit).grid(
            row=0, column=2
        )

        # Row 1: Firmware
        self._firmware_var = tk.StringVar()
        ttk.Label(settings_frame, text="Firmware:").grid(
            row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0)
        )
        ttk.Entry(settings_frame, textvariable=self._firmware_var, width=52).grid(
            row=1, column=1, sticky="ew", padx=(0, 4), pady=(4, 0)
        )
        ttk.Button(settings_frame, text="Browse...", command=self._browse_firmware).grid(
            row=1, column=2, pady=(4, 0)
        )

        # Row 2: Config
        self._config_path_var = tk.StringVar()
        ttk.Label(settings_frame, text="Config:").grid(
            row=2, column=0, sticky="w", padx=(0, 4), pady=(4, 0)
        )
        ttk.Entry(settings_frame, textvariable=self._config_path_var, width=52).grid(
            row=2, column=1, sticky="ew", padx=(0, 4), pady=(4, 0)
        )
        ttk.Button(settings_frame, text="Browse...", command=self._browse_config).grid(
            row=2, column=2, pady=(4, 0)
        )

        # Row 3: Username / Password
        self._username_var = tk.StringVar()
        self._password_var = tk.StringVar()
        cred_frame = ttk.Frame(settings_frame)
        cred_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(cred_frame, text="Username:").pack(side="left")
        ttk.Entry(cred_frame, textvariable=self._username_var, width=18).pack(
            side="left", padx=(4, 16)
        )
        ttk.Label(cred_frame, text="Password:").pack(side="left")
        ttk.Entry(cred_frame, textvariable=self._password_var, width=18, show="*").pack(
            side="left", padx=(4, 16)
        )
        self._remember_var = tk.BooleanVar()
        ttk.Checkbutton(cred_frame, text="Remember", variable=self._remember_var).pack(side="left")

        # Row 4: CAN / BLE / Network
        conn_frame = ttk.Frame(settings_frame)
        conn_frame.grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(conn_frame, text="CAN Baudrate:").pack(side="left")
        self._can_baudrate_var = tk.StringVar()
        ttk.Combobox(
            conn_frame,
            textvariable=self._can_baudrate_var,
            values=_CAN_BAUDRATES,
            width=14,
            state="readonly",
        ).pack(side="left", padx=(4, 16))

        ttk.Label(conn_frame, text="Start Node ID:").pack(side="left")
        self._node_id_var = tk.IntVar(value=0)
        ttk.Spinbox(conn_frame, textvariable=self._node_id_var, from_=0, to=127, width=6).pack(
            side="left", padx=(4, 16)
        )

        ttk.Label(conn_frame, text="BLE:").pack(side="left")
        self._ble_var = tk.StringVar()
        ttk.Combobox(
            conn_frame,
            textvariable=self._ble_var,
            values=_BLE_MODES,
            width=10,
            state="readonly",
        ).pack(side="left", padx=(4, 16))

        ttk.Label(conn_frame, text="Network:").pack(side="left")
        self._network_var = tk.StringVar()
        ttk.Combobox(
            conn_frame,
            textvariable=self._network_var,
            values=_NETWORK_MODES,
            width=10,
            state="readonly",
        ).pack(side="left", padx=(4, 0))

        # Row 5: Toolkit status indicator
        status_frame = ttk.Frame(settings_frame)
        status_frame.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Label(status_frame, text="Toolkit Status:").pack(side="left")
        self._toolkit_status_label = ttk.Label(status_frame, text="○ Disconnected")
        self._toolkit_status_label.pack(side="left", padx=(4, 0))

        settings_frame.columnconfigure(1, weight=1)

        # --- Board Processing section ---
        processing_frame = ttk.LabelFrame(self, text="Board Processing", padding=8)
        processing_frame.pack(fill="x", **pad)

        # Serial number row
        serial_row = ttk.Frame(processing_frame)
        serial_row.pack(fill="x")
        ttk.Label(serial_row, text="Serial Number:").pack(side="left")
        self._serial_var = tk.StringVar()
        self._serial_entry = ttk.Entry(serial_row, textvariable=self._serial_var, width=28)
        self._serial_entry.pack(side="left", padx=(4, 8))
        self._serial_entry.bind("<Return>", lambda _e: self._on_start())

        self._start_btn = ttk.Button(
            serial_row, text="\u25b6 Start", command=self._on_start, width=10
        )
        self._start_btn.pack(side="left", padx=(0, 8))

        self._cancel_btn = ttk.Button(
            serial_row, text="Cancel", command=self._on_cancel, state="disabled", width=8
        )
        self._cancel_btn.pack(side="left")

        # Pipeline step indicators
        pipeline_frame = ttk.Frame(processing_frame)
        pipeline_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(pipeline_frame, text="Pipeline:").pack(side="left")

        from wattius_commissioning_tool.models import CommissioningStep

        _step_enum_map = {member.name: member for member in CommissioningStep}
        for step_name, display in _STEP_LABELS:
            lbl = ttk.Label(pipeline_frame, text=f"\u25cb {display}", padding=(6, 0))
            lbl.pack(side="left")
            self._step_labels[step_name] = lbl

        # Progress bar
        prog_frame = ttk.Frame(processing_frame)
        prog_frame.pack(fill="x", pady=(8, 0))
        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(prog_frame, variable=self._progress_var, maximum=100)
        self._progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._progress_label = ttk.Label(prog_frame, text="Ready")
        self._progress_label.pack(side="right")

        # Log area
        log_frame = ttk.LabelFrame(processing_frame, text="Log", padding=4)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))

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

        # --- Session Summary section ---
        summary_frame = ttk.LabelFrame(self, text="Session Summary", padding=8)
        summary_frame.pack(fill="both", expand=True, **pad)

        columns = ("serial", "can_id", "status", "time")
        self._summary_tree = ttk.Treeview(
            summary_frame,
            columns=columns,
            show="headings",
            height=6,
            selectmode="browse",
        )
        self._summary_tree.heading("serial", text="Serial Number")
        self._summary_tree.heading("can_id", text="CAN ID")
        self._summary_tree.heading("status", text="Status")
        self._summary_tree.heading("time", text="Completed")

        self._summary_tree.column("serial", width=200, minwidth=120)
        self._summary_tree.column("can_id", width=80, minwidth=60, anchor="center")
        self._summary_tree.column("status", width=80, minwidth=60, anchor="center")
        self._summary_tree.column("time", width=160, minwidth=100)

        tree_scroll = ttk.Scrollbar(
            summary_frame, orient="vertical", command=self._summary_tree.yview
        )
        self._summary_tree.configure(yscrollcommand=tree_scroll.set)
        self._summary_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Stats row
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill="x", padx=8, pady=(0, 4))
        self._stats_label = ttk.Label(stats_frame, text="Total: 0  Pass: 0  Fail: 0")
        self._stats_label.pack(side="left")
        self._export_btn = ttk.Button(
            stats_frame, text="Export Log", command=self._on_export_log, state="disabled"
        )
        self._export_btn.pack(side="right")

        # Session tracking
        self._total_count = 0
        self._pass_count = 0
        self._fail_count = 0

    # ------------------------------------------------------------------
    # Config load / save
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        c = self._config
        self._toolkit_var.set(c.toolkit_path)
        self._firmware_var.set(c.firmware_path)
        self._config_path_var.set(c.config_path)
        self._username_var.set(c.username)
        self._password_var.set(c.password if c.remember_password else "")
        self._remember_var.set(c.remember_password)
        self._can_baudrate_var.set(c.can_baudrate)
        self._node_id_var.set(c.base_can_node_id)
        self._ble_var.set(c.ble_mode)
        self._network_var.set(c.network_mode)

    def _save_config(self) -> None:
        self._config.toolkit_path = self._toolkit_var.get()
        self._config.firmware_path = self._firmware_var.get()
        self._config.config_path = self._config_path_var.get()
        self._config.username = self._username_var.get()
        self._config.remember_password = self._remember_var.get()
        if self._config.remember_password:
            self._config.password = self._password_var.get()
        else:
            self._config.password = ""
        self._config.can_baudrate = self._can_baudrate_var.get()
        self._config.base_can_node_id = self._node_id_var.get()
        self._config.ble_mode = self._ble_var.get()
        self._config.network_mode = self._network_var.get()

    # ------------------------------------------------------------------
    # Browse handlers
    # ------------------------------------------------------------------

    def _browse_toolkit(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Wattius Toolkit",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")],
        )
        if path:
            self._toolkit_var.set(path)

    def _browse_firmware(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Firmware File",
            filetypes=[("SREC Firmware", "*.srec"), ("All Files", "*.*")],
        )
        if path:
            self._firmware_var.set(path)

    def _browse_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Config File",
            filetypes=[("Wattius Config", "*.wconf"), ("All Files", "*.*")],
        )
        if path:
            self._config_path_var.set(path)

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
                        self._progress_label.configure(text=f"{current}/{total}")
                    else:
                        self._progress_var.set(0)
                        self._progress_label.configure(text="Ready")
                elif msg_type == "step":
                    step, status = data
                    self._update_step_label(step, status)
                elif msg_type == "board_done":
                    self._on_board_done(data)
                elif msg_type == "error":
                    self._append_log(f"ERROR: {data}")
                    self._on_worker_done()
                elif msg_type == "toolkit_status":
                    connected: bool = data
                    if connected:
                        self._toolkit_status_label.configure(text="\u25cf Connected")
                    else:
                        self._toolkit_status_label.configure(text="\u25cb Disconnected")
        except queue.Empty:
            pass
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def _append_log(self, message: object) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", str(message) + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _update_step_label(self, step: "CommissioningStep", status: str) -> None:
        lbl = self._step_labels.get(step.name)
        if lbl is None:
            return
        display = dict(_STEP_LABELS).get(step.name, step.name)
        if status == "running":
            lbl.configure(text=f"\u25ba {display}")
        elif status == "pass":
            lbl.configure(text=f"\u2713 {display}")
        elif status == "fail":
            lbl.configure(text=f"\u2717 {display}")
        else:
            lbl.configure(text=f"\u25cb {display}")

    def _reset_step_labels(self) -> None:
        for step_name, display in _STEP_LABELS:
            lbl = self._step_labels.get(step_name)
            if lbl:
                lbl.configure(text=f"\u25cb {display}")

    # ------------------------------------------------------------------
    # Board done handling
    # ------------------------------------------------------------------

    def _on_board_done(self, result: "BoardResult") -> None:
        completed_time = result.completed_at[:19].replace("T", " ")
        self._summary_tree.insert(
            "",
            "end",
            values=(result.serial_number, result.can_node_id, result.status, completed_time),
        )
        self._summary_tree.yview_moveto(1.0)

        self._total_count += 1
        if result.status == "PASS":
            self._pass_count += 1
        else:
            self._fail_count += 1
        self._stats_label.configure(
            text=f"Total: {self._total_count}  Pass: {self._pass_count}  Fail: {self._fail_count}"
        )

        if self._session is not None:
            self._session.board_index += 1

        self._on_worker_done()
        self._serial_var.set("")
        self._serial_entry.focus_set()

    # ------------------------------------------------------------------
    # Button state management
    # ------------------------------------------------------------------

    def _set_working(self, working: bool) -> None:
        state = "disabled" if working else "normal"
        self._start_btn.configure(state=state)
        self._cancel_btn.configure(state="normal" if working else "disabled")

    def _on_worker_done(self) -> None:
        self._set_working(False)
        self._worker_thread = None
        self._progress_label.configure(text="Ready")

    # ------------------------------------------------------------------
    # Start / Cancel
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        serial = self._serial_var.get().strip()
        if not serial:
            self._append_log("Enter a serial number first.")
            return
        if self._worker_thread and self._worker_thread.is_alive():
            return

        # Sync config from fields
        self._save_config()

        # Initialise session on first board
        if self._session is None:
            from wattius_commissioning_tool.commissioning_log import CommissioningLogger
            from wattius_commissioning_tool.models import SessionState

            self._session = SessionState(
                board_index=0,
                session_start=datetime.now().isoformat(),
            )
            self._logger = CommissioningLogger(self._config.log_directory)
            self._logger.start_session()
            self._export_btn.configure(state="normal")

        self._reset_step_labels()
        self._set_working(True)
        self._cancel_event.clear()
        self._progress_var.set(0)
        self._progress_label.configure(text="Processing...")

        self._worker_thread = Thread(target=self._commission_worker, args=(serial,), daemon=True)
        self._worker_thread.start()

    def _on_cancel(self) -> None:
        self._cancel_event.set()
        self._append_log("Cancelling...")

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _commission_worker(self, serial: str) -> None:
        from wattius_commissioning_tool.orchestrator import CommissioningOrchestrator
        from wattius_commissioning_tool.toolkit_manager import ToolkitManager

        try:
            if not self._toolkit_manager or not self._toolkit_manager.is_running():
                self._queue.put(("log", "Starting Toolkit..."))
                self._toolkit_manager = ToolkitManager(
                    self._config.toolkit_path,
                    self._config.username,
                    self._config.password,
                )
                self._toolkit_manager.start()
                if not self._toolkit_manager.wait_ready():
                    self._queue.put(("error", "Toolkit failed to start"))
                    return
                if not self._toolkit_manager.sign_in():
                    self._queue.put(("error", "Toolkit sign-in failed"))
                    return
                self._queue.put(("toolkit_status", True))

            can_node_id = self._config.base_can_node_id + (
                self._session.board_index if self._session else 0
            )

            orchestrator = CommissioningOrchestrator(
                progress_callback=lambda c, t: self._queue.put(("progress", (c, t))),
                log_callback=lambda m: self._queue.put(("log", m)),
                step_callback=lambda s, st: self._queue.put(("step", (s, st))),
            )

            result = orchestrator.process_board(
                serial_number=serial,
                can_node_id=can_node_id,
                config=self._config,
                cancel_event=self._cancel_event,
            )

            if self._logger:
                self._logger.log_board(result)
            self._queue.put(("board_done", result))
        except Exception as e:
            logging.getLogger(__name__).exception("Commission worker failed")
            self._queue.put(("error", str(e)))

    # ------------------------------------------------------------------
    # Export log
    # ------------------------------------------------------------------

    def _on_export_log(self) -> None:
        if self._logger and self._logger.session_path:
            os.startfile(self._logger.session_path)

    # ------------------------------------------------------------------
    # Shell interface
    # ------------------------------------------------------------------

    def start_polling(self) -> None:
        """Start the queue poller. Called by the shell after the tab is placed."""
        self.after(self.POLL_INTERVAL_MS, self._process_queue)

    def close(self) -> None:
        """Called by the shell on window close."""
        self._save_config()
        if self._worker_thread and self._worker_thread.is_alive():
            self._cancel_event.set()
        if self._toolkit_manager:
            self._toolkit_manager.stop()
