from __future__ import annotations

import logging
import time
from asyncio import CancelledError
from datetime import datetime
from threading import Event
from typing import Callable

from inventor_utils.base_orchestrator import BaseOrchestrator

from wattius_commissioning_tool.config import CommissioningConfig
from wattius_commissioning_tool.models import BoardResult, CommissioningStep

logger = logging.getLogger("zabra.commissioning")

StepCallback = Callable[[CommissioningStep, str], None]

_TOTAL_STEPS = 6


def _zero_pad_ip(ip: str) -> str:
    return ".".join(part.zfill(3) for part in ip.split("."))


class CommissioningOrchestrator(BaseOrchestrator):
    """Processes a single BMU board through the 6-step commissioning pipeline."""

    def __init__(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
        step_callback: StepCallback | None = None,
    ) -> None:
        super().__init__(progress_callback, log_callback)
        self._step_cb: StepCallback = step_callback or (lambda s, st: None)

    def _notify_step(self, step: CommissioningStep, status: str) -> None:
        self._step_cb(step, status)

    def _poll_until_done(
        self,
        fn: Callable,
        timeout_s: float,
        step_name: str,
        cancel_event: Event,
    ):
        """Poll fn() until it returns OK, ERROR, or TIMEOUT (not WAITING/GETTING)."""
        from wbms_api.wbms_toolkit_types import wbms_result

        result = wbms_result.WAITING
        start = time.monotonic()
        while result not in (wbms_result.OK, wbms_result.ERROR, wbms_result.TIMEOUT):
            if cancel_event.is_set():
                raise CancelledError(f"{step_name} cancelled")
            if time.monotonic() - start > timeout_s:
                raise TimeoutError(f"{step_name} timed out after {timeout_s}s")
            time.sleep(0.5)
            result = fn()
        return result

    def _poll_crc(
        self,
        fn: Callable,
        timeout_s: float,
        cancel_event: Event,
    ) -> str:
        """Poll fn() until it returns something other than wbms_result.WAITING."""
        from wbms_api.wbms_toolkit_types import wbms_result

        start = time.monotonic()
        while True:
            if cancel_event.is_set():
                raise CancelledError("TESTING cancelled")
            if time.monotonic() - start > timeout_s:
                raise TimeoutError(f"TESTING timed out after {timeout_s}s")
            time.sleep(0.5)
            result = fn()
            if result is not wbms_result.WAITING:
                return str(result)

    def process_board(
        self,
        serial_number: str,
        can_node_id: int,
        config: CommissioningConfig,
        cancel_event: Event,
    ) -> BoardResult:
        """Run all 6 commissioning steps for a single BMU board."""
        from wbms_api.wbms_toolkit_api import (
            wbms_apply_setup,
            wbms_get_config_crc,
            wbms_set_connection_usb,
            wbms_update_firmware,
            wbms_upload_config,
        )
        from wbms_api.wbms_toolkit_types import (
            wbms_ble_mode,
            wbms_can_baudrate,
            wbms_network_mode,
            wbms_result,
        )

        started_at = datetime.now().isoformat()
        config_crc: str | None = None
        failure_step: str | None = None
        failure_reason: str | None = None
        firmware_version: str = ""

        today = datetime.now().strftime("%d/%m/%y")
        manufacturing_date = config.manufacturing_date if config.manufacturing_date else today

        def _fail(step: CommissioningStep, reason: str) -> BoardResult:
            nonlocal failure_step, failure_reason
            failure_step = step.value
            failure_reason = reason
            logger.error("Board %s failed at %s: %s", serial_number, step.value, reason)
            self._emit(f"[FAIL] {step.value}: {reason}")
            self._notify_step(step, "fail")
            return BoardResult(
                serial_number=serial_number,
                can_node_id=can_node_id,
                firmware_version=firmware_version,
                config_crc=config_crc,
                status="FAIL",
                failure_step=failure_step,
                failure_reason=failure_reason,
                started_at=started_at,
                completed_at=datetime.now().isoformat(),
            )

        # --- Step 1: CONNECTING ---
        step = CommissioningStep.CONNECTING
        self._progress(1, _TOTAL_STEPS)
        self._notify_step(step, "running")
        self._emit(f"[{step.value}] Connecting via USB...")
        logger.info("Board %s: %s", serial_number, step.value)
        try:
            result = wbms_set_connection_usb()
            if result != wbms_result.OK:
                return _fail(step, f"wbms_set_connection_usb returned {result}")
        except CancelledError:
            return _fail(step, "cancelled")
        except Exception as exc:
            return _fail(step, str(exc))
        self._notify_step(step, "pass")
        self._emit(f"[{step.value}] Connected.")

        # --- Step 2: FLASHING ---
        step = CommissioningStep.FLASHING
        self._progress(2, _TOTAL_STEPS)
        self._notify_step(step, "running")
        self._emit(f"[{step.value}] Flashing firmware: {config.firmware_path}")
        logger.info("Board %s: %s", serial_number, step.value)
        try:
            if cancel_event.is_set():
                return _fail(step, "cancelled")
            result = wbms_update_firmware(config.firmware_path)
            if result != wbms_result.OK:
                return _fail(step, f"wbms_update_firmware returned {result}")
        except CancelledError:
            return _fail(step, "cancelled")
        except Exception as exc:
            return _fail(step, str(exc))
        self._notify_step(step, "pass")
        self._emit(f"[{step.value}] Firmware flashed.")

        # --- Step 3: CONFIGURING ---
        step = CommissioningStep.CONFIGURING
        self._progress(3, _TOTAL_STEPS)
        self._notify_step(step, "running")
        self._emit(f"[{step.value}] Uploading config: {config.config_path}")
        logger.info("Board %s: %s", serial_number, step.value)
        try:
            result = self._poll_until_done(
                lambda: wbms_upload_config(config.config_path),
                90.0,
                step.value,
                cancel_event,
            )
            if result != wbms_result.OK:
                return _fail(step, f"wbms_upload_config returned {result}")
        except CancelledError:
            return _fail(step, "cancelled")
        except TimeoutError as exc:
            return _fail(step, str(exc))
        except Exception as exc:
            return _fail(step, str(exc))
        self._notify_step(step, "pass")
        self._emit(f"[{step.value}] Config uploaded.")

        # --- Step 4: APPLYING_SETUP ---
        step = CommissioningStep.APPLYING_SETUP
        self._progress(4, _TOTAL_STEPS)
        self._notify_step(step, "running")
        self._emit(f"[{step.value}] Applying BMU setup (node_id={can_node_id})...")
        logger.info("Board %s: %s", serial_number, step.value)
        try:
            baudrate_enum = wbms_can_baudrate[config.can_baudrate]
            ble_enum = wbms_ble_mode[config.ble_mode]
            network_enum = wbms_network_mode[config.network_mode]
            static_ip = _zero_pad_ip(config.static_ip)
            netmask = _zero_pad_ip(config.netmask)
            gateway = _zero_pad_ip(config.gateway)
            dns1 = _zero_pad_ip(config.dns1)
            dns2 = _zero_pad_ip(config.dns2)

            result = self._poll_until_done(
                lambda: wbms_apply_setup(
                    baudrate_enum,
                    can_node_id,
                    ble_enum,
                    network_enum,
                    static_ip,
                    netmask,
                    gateway,
                    dns1,
                    dns2,
                    "1",
                    manufacturing_date,
                    today,
                ),
                60.0,
                step.value,
                cancel_event,
            )
            if result != wbms_result.OK:
                return _fail(step, f"wbms_apply_setup returned {result}")
        except CancelledError:
            return _fail(step, "cancelled")
        except TimeoutError as exc:
            return _fail(step, str(exc))
        except Exception as exc:
            return _fail(step, str(exc))
        self._notify_step(step, "pass")
        self._emit(f"[{step.value}] Setup applied.")

        # --- Step 5: TESTING ---
        step = CommissioningStep.TESTING
        self._progress(5, _TOTAL_STEPS)
        self._notify_step(step, "running")
        self._emit(f"[{step.value}] Verifying config CRC...")
        logger.info("Board %s: %s", serial_number, step.value)
        try:
            config_crc = self._poll_crc(wbms_get_config_crc, 30.0, cancel_event)
        except CancelledError:
            return _fail(step, "cancelled")
        except TimeoutError as exc:
            return _fail(step, str(exc))
        except Exception as exc:
            return _fail(step, str(exc))
        self._notify_step(step, "pass")
        self._emit(f"[{step.value}] CRC verified: {config_crc}")

        # --- Step 6: LOGGING ---
        step = CommissioningStep.LOGGING
        self._progress(6, _TOTAL_STEPS)
        self._notify_step(step, "running")
        self._emit(f"[{step.value}] Recording result...")
        logger.info("Board %s: PASS (CRC=%s)", serial_number, config_crc)
        self._notify_step(step, "pass")
        self._emit(f"[{step.value}] Done.")

        return BoardResult(
            serial_number=serial_number,
            can_node_id=can_node_id,
            firmware_version=firmware_version,
            config_crc=config_crc,
            status="PASS",
            failure_step=None,
            failure_reason=None,
            started_at=started_at,
            completed_at=datetime.now().isoformat(),
        )
