# Wattius BMU Commissioning Tool — Design Spec

**Date:** 2026-03-18
**Status:** Implemented
**Package:** `wattius_commissioning_tool`

## Context

We need to automate the full commissioning pipeline for wBMS-MX-Pro BMU PCBs. Today this is done manually through the Wattius Toolkit GUI — one board at a time: flash firmware, upload config, apply setup, run end-of-line test. This is slow and error-prone.

The Wattius `wbms_api` (v1.0.0) provides a Python API that communicates via IPv6 socket (localhost:11000) to the Toolkit application, enabling full automation of every step. We'll build a new Zabra-Cadabra tab that wraps this API into a streamlined production commissioning workflow with barcode scanning, auto-incrementing CAN node IDs, and structured logging.

## Requirements

- **USB one-at-a-time**: Operator plugs in one BMU, scans barcode, tool does everything, operator unplugs
- **Auto-incrementing CAN node ID**: Each board gets `base_id + board_index`
- **Full pipeline**: Flash firmware → upload config → apply setup → EOL test → log
- **Barcode scanner input**: USB barcode scanner types serial number + Enter
- **Local CSV logging**: Per-session CSV file with serial, CAN ID, status, timestamps
- **Toolkit process management**: Auto-launch and manage the Toolkit .exe in background
- **GUI tab**: Embedded in Zabra-Cadabra, following existing tab patterns
- **CLI**: Standalone CLI for headless/scripted use

## Architecture

### Package Structure

```
wattius_commissioning_tool/
  pyproject.toml
  src/wattius_commissioning_tool/
    __init__.py
    __main__.py                     # Calls cli.main()
    cli.py                          # argparse CLI entry point
    gui.py                          # CommissioningToolGUI (ttk.Frame tab)
    models.py                       # BoardResult, CommissioningStep enum, SessionState
    config.py                       # JSON config persistence
    orchestrator.py                 # 6-step pipeline, extends BaseOrchestrator
    toolkit_manager.py              # Start/stop/poll Toolkit .exe process
    commissioning_log.py            # CSV session logging
  tests/
    conftest.py
    test_models.py
    test_config.py
    test_orchestrator.py
    test_toolkit_manager.py
    test_commissioning_log.py
```

**Dependencies:**
- `wbms_api` — installed from `.whl` file via `[tool.uv.sources]` path reference
- `inventor-utils` — reuse `BaseOrchestrator`, `config` helpers (workspace dep)

### Integration Points

- **Tab registry:** New `TabSpec` in `zabra_cadabra/src/zabra_cadabra/tab_registry.py`
- **Workspace member:** Add to root `pyproject.toml`
- **Shell dependency:** Add to `zabra_cadabra/pyproject.toml`
- **Config loader:** Add in `zabra_cadabra/src/zabra_cadabra/app.py`

## Detailed Design

### 1. Pipeline (orchestrator.py)

Extends `BaseOrchestrator` from `inventor_utils/src/inventor_utils/base_orchestrator.py`.

**State machine:**
```
IDLE → CONNECTING → FLASHING → CONFIGURING → APPLYING_SETUP → TESTING → LOGGING → DONE/FAILED
```

**Step details:**

| Step | API Call | Timeout | Pattern |
|------|----------|---------|---------|
| CONNECTING | `wbms_set_connection_usb()` | 10s | Simple |
| FLASHING | `wbms_update_firmware(firmware_path)` | 360s (6 min) | Simple |
| CONFIGURING | `wbms_upload_config(config_path)` | 90s | Polling (WAITING→OK) |
| APPLYING_SETUP | `wbms_apply_setup(...)` | 60s | Polling (WAITING→OK) |
| TESTING | `wbms_get_config_crc()` | 30s | Polling (WAITING→CRC string) |
| LOGGING | BoardResult creation | N/A | Sync |

**Polling pattern** (reused across config/setup steps):
```python
def _poll_until_done(self, fn, timeout_s, step_name, cancel_event):
    result = wbms_result.WAITING
    start = time.monotonic()
    while result not in (wbms_result.OK, wbms_result.ERROR, wbms_result.TIMEOUT):
        if cancel_event.is_set():
            raise CancelledError(f"{step_name} cancelled")
        if time.monotonic() - start > timeout_s:
            raise TimeoutError(f"{step_name} timed out after {timeout_s}s")
        time.sleep(0.5)  # Prevent tight CPU spin
        result = fn()
    return result
```

**CRC polling** uses a separate `_poll_crc()` method since `wbms_get_config_crc()` returns a string CRC value (not `wbms_result.OK`) when complete.

**cancel_event** is passed as a parameter to `process_board()`, not stored as an instance attribute (matches `DrawingCreationOrchestrator.execute()` pattern).

**IP address zero-padding:** Config stores `"0.0.0.0"`, orchestrator zero-pads to `"000.000.000.000"` for the `wbms_apply_setup()` API call via `_zero_pad_ip()` helper.

**apply_setup parameters:**
- `can_baudrate`: From config enum string → `wbms_can_baudrate[config.can_baudrate]`
- `can_node_id`: `base_can_node_id + board_index`
- `ble_mode`: From config → `wbms_ble_mode[config.ble_mode]`
- `network_mode`: From config → `wbms_network_mode[config.network_mode]`
- `apply_dates`: `"1"`
- `manufacturing_date`: From config or today (`DD/MM/YY`)
- `commissioning_date`: Today's date (`DD/MM/YY` format)

**On failure:** Board marked FAIL with step name and error message. Pipeline stops. Operator can retry or skip.

### 2. Toolkit Manager (toolkit_manager.py)

```python
class ToolkitManager:
    def __init__(self, toolkit_path: str, username: str, password: str): ...
    def start(self) -> None:          # Launch .exe via subprocess.Popen (CREATE_NO_WINDOW)
    def wait_ready(self, timeout=30) -> bool:  # Poll with wbms_toolkit_api_poll()
    def sign_in(self) -> bool:        # wbms_sign_in(username, password)
    def stop(self) -> None:           # Terminate process, kill on timeout
    def is_running(self) -> bool:     # Check process status
```

- Uses `subprocess.CREATE_NO_WINDOW` flag on Windows
- `start()` skips if already running
- `stop()` calls `terminate()` then `wait(timeout=10)`, falls back to `kill()`

### 3. Data Models (models.py)

```python
class CommissioningStep(Enum):
    CONNECTING = "connecting"
    FLASHING = "flashing"
    CONFIGURING = "configuring"
    APPLYING_SETUP = "applying_setup"
    TESTING = "testing"
    LOGGING = "logging"

@dataclass
class BoardResult:
    serial_number: str
    can_node_id: int
    firmware_version: str
    config_crc: str | None
    status: str                     # "PASS" or "FAIL"
    failure_step: str | None
    failure_reason: str | None
    started_at: str                 # ISO 8601
    completed_at: str               # ISO 8601

@dataclass
class SessionState:
    board_index: int = 0
    session_start: str = ""
    results: list[BoardResult] = field(default_factory=list)
```

`SessionState` owns `board_index` (for auto-incrementing CAN node IDs), `session_start`, and the list of `BoardResult` objects. The GUI owns the `SessionState` instance and passes `board_index` to the orchestrator.

### 4. Config (config.py)

JSON file, same pattern as `inventor_export_tool/config.py`. Uses `get_config_path()` for default path.

```python
@dataclass
class CommissioningConfig:
    toolkit_path: str = ""
    firmware_path: str = ""
    config_path: str = ""
    username: str = ""
    password: str = ""
    remember_password: bool = False  # Only persist password if True
    can_baudrate: str = "CAN_500kbps"
    base_can_node_id: int = 0
    ble_mode: str = "DISABLED"
    network_mode: str = "DISABLE"
    static_ip: str = "0.0.0.0"
    netmask: str = "0.0.0.0"
    gateway: str = "0.0.0.0"
    dns1: str = "0.0.0.0"
    dns2: str = "0.0.0.0"
    manufacturing_date: str = ""
    log_directory: str = "logs"
    auto_start_on_scan: bool = True
```

**Password handling:** `save_config()` clears the password field before persisting when `remember_password=False`. Uses `copy.copy()` to avoid mutating the caller's config object.

### 5. GUI (gui.py)

`CommissioningToolGUI(ttk.Frame)` — follows `DrawingToolGUI` pattern.

**Layout:**

```
┌─ Settings ──────────────────────────────────────────┐
│ Toolkit Path: [________________________] [Browse]   │
│ Firmware:     [________________________] [Browse]   │
│ Config:       [________________________] [Browse]   │
│ Username: [________]  Password: [********]          │
│ CAN Baudrate: [500K ▼]  Start Node ID: [0 ▲▼]     │
│ BLE: [Disabled ▼]  Network: [Disabled ▼]           │
│ Toolkit Status: [● Connected / ○ Disconnected]     │
├─ Board Processing ──────────────────────────────────┤
│ Serial Number: [____________________] [▶ Start]     │
│                                                     │
│ Pipeline: ○ Connect  ○ Flash  ○ Config  ○ Setup    │
│           ○ Test     ○ Log                          │
│                                                     │
│ ┌─ Log ───────────────────────────────────────────┐ │
│ │ [scrolling text log]                            │ │
│ └─────────────────────────────────────────────────┘ │
├─ Session Summary ───────────────────────────────────┤
│ [Treeview: Serial | CAN ID | Status | Completed]   │
│                                                     │
│ Total: 3  Pass: 2  Fail: 1     [Export Log]        │
└─────────────────────────────────────────────────────┘
```

**Key behaviors:**
- Serial number Entry auto-focused after each board completes
- `<Return>` triggers pipeline (barcode scanner sends Enter)
- Pipeline step indicators: ○ pending, ► running, ✓ pass, ✗ fail
- Toolkit status indicator: ● Connected / ○ Disconnected
- Worker thread runs orchestrator; GUI polls queue (100ms interval)
- Cancel button available during processing
- Toolkit auto-launched on first board scan if not running

### 6. Session Logging (commissioning_log.py)

Standalone class using `csv.writer` directly (does NOT extend `ToolLogger` — CSV is the right format for tabular commissioning data).

```python
class CommissioningLogger:
    def __init__(self, log_directory: str): ...
    def start_session(self) -> None:     # Create CSV with header
    def log_board(self, result: BoardResult) -> None:  # Append row
    def end_session(self) -> str:        # Return file path
    @property
    def session_path(self) -> str | None
```

**CSV format:** `commissioning_20260318_143200.csv`
```
serial_number,can_node_id,firmware_version,config_crc,status,failure_step,failure_reason,started_at,completed_at
```

### 7. CLI (cli.py)

```
wattius-commission --firmware path.srec --config path.wconf --serial ABC123 --toolkit path.exe [options]
```

Returns exit code 0 on PASS, 1 on FAIL.

## Files Created/Modified

### New Files
- `wattius_commissioning_tool/pyproject.toml`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/__init__.py`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/__main__.py`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/cli.py`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/gui.py`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/models.py`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/config.py`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/orchestrator.py`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/toolkit_manager.py`
- `wattius_commissioning_tool/src/wattius_commissioning_tool/commissioning_log.py`
- `wattius_commissioning_tool/tests/conftest.py`
- `wattius_commissioning_tool/tests/test_models.py`
- `wattius_commissioning_tool/tests/test_config.py`
- `wattius_commissioning_tool/tests/test_orchestrator.py`
- `wattius_commissioning_tool/tests/test_toolkit_manager.py`
- `wattius_commissioning_tool/tests/test_commissioning_log.py`

### Modified Files
- `pyproject.toml` (root) — Add workspace member
- `zabra_cadabra/pyproject.toml` — Add dependency
- `zabra_cadabra/src/zabra_cadabra/tab_registry.py` — Add TabSpec
- `zabra_cadabra/src/zabra_cadabra/app.py` — Add config loader

## Verification

1. **Unit tests:** `uv run --package wattius-commissioning-tool pytest` — 48 tests passing
2. **Lint:** `uv run ruff check wattius_commissioning_tool` — all checks passed
3. **Format:** `uv run ruff format --check wattius_commissioning_tool` — 15 files formatted
4. **Integration:** `uv sync --all-packages` then `uv run zabra-cadabra` — verify tab appears
5. **Manual E2E:** Connect real BMU via USB, run through full pipeline, verify CSV log output
