from __future__ import annotations

import argparse
import sys
from threading import Event

from wattius_commissioning_tool.commissioning_log import CommissioningLogger
from wattius_commissioning_tool.config import CommissioningConfig
from wattius_commissioning_tool.orchestrator import CommissioningOrchestrator
from wattius_commissioning_tool.toolkit_manager import ToolkitManager


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wattius-commission",
        description="Wattius BMU commissioning tool — flash, configure, and test BMU boards.",
    )
    parser.add_argument("--firmware", required=True, help="Path to .srec firmware file")
    parser.add_argument("--config", required=True, help="Path to .wconf config template")
    parser.add_argument("--serial", required=True, help="Board serial number (from barcode)")
    parser.add_argument("--toolkit", required=True, help="Path to wBMS-Toolkit .exe")
    parser.add_argument("--username", default="", help="Toolkit sign-in username")
    parser.add_argument("--password", default="", help="Toolkit sign-in password")
    parser.add_argument(
        "--can-baudrate",
        default="CAN_500kbps",
        help="CAN baudrate (default: CAN_500kbps)",
    )
    parser.add_argument(
        "--can-node-id",
        type=int,
        default=0,
        help="CAN node ID for this board (default: 0)",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for result logs (default: logs)",
    )

    args = parser.parse_args()

    config = CommissioningConfig(
        toolkit_path=args.toolkit,
        firmware_path=args.firmware,
        config_path=args.config,
        username=args.username,
        password=args.password,
        can_baudrate=args.can_baudrate,
        base_can_node_id=args.can_node_id,
        log_directory=args.log_dir,
    )

    def log_callback(msg: str) -> None:
        print(msg)

    def progress_callback(current: int, total: int) -> None:
        if total > 0:
            pct = current * 100 // total
            print(f"  [{current}/{total}] {pct}%")

    toolkit = ToolkitManager(
        toolkit_path=config.toolkit_path,
        username=config.username,
        password=config.password,
    )

    try:
        print(f"Starting Wattius Toolkit: {config.toolkit_path}")
        toolkit.start()

        print("Waiting for toolkit to become ready...")
        if not toolkit.wait_ready():
            print("ERROR: Toolkit did not become ready in time.")
            sys.exit(1)

        print("Signing in...")
        if not toolkit.sign_in():
            print("ERROR: Toolkit sign-in failed.")
            sys.exit(1)

        orchestrator = CommissioningOrchestrator(
            progress_callback=progress_callback,
            log_callback=log_callback,
        )

        log = CommissioningLogger(log_directory=config.log_directory)
        log.start_session()

        print(f"\nCommissioning board: {args.serial} (node_id={args.can_node_id})")
        result = orchestrator.process_board(
            serial_number=args.serial,
            can_node_id=args.can_node_id,
            config=config,
            cancel_event=Event(),
        )

        log.log_board(result)
        log_path = log.end_session()

        print()
        print(f"Result: {result.status}")
        if result.failure_step:
            print(f"  Failed at: {result.failure_step}")
        if result.failure_reason:
            print(f"  Reason: {result.failure_reason}")
        if result.config_crc:
            print(f"  Config CRC: {result.config_crc}")
        print(f"Log: {log_path}")

    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    finally:
        toolkit.stop()

    if result.status == "PASS":
        sys.exit(0)
    else:
        sys.exit(1)
