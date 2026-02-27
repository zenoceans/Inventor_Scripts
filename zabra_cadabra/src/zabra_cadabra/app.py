"""Zabra-Cadabra application entry point."""

from __future__ import annotations

import sys


def main() -> None:
    if sys.platform != "win32":
        print("Zabra-Cadabra requires Windows.")
        sys.exit(1)

    from inventor_drawing_tool.config import load_drawing_config, save_drawing_config
    from inventor_export_tool.config import load_config, save_config
    from inventor_simplify_tool.config import load_simplify_config, save_simplify_config
    from zabra_cadabra.shell import ZabraApp
    from zabra_cadabra.telemetry import (
        SessionContext,
        load_telemetry_config,
        log_event,
        save_telemetry_config,
        setup_logging,
    )
    from zabra_cadabra.telemetry.transport import NetworkTransport

    inventor_config = load_config()
    simplify_config = load_simplify_config()
    drawing_config = load_drawing_config()
    tel_config = load_telemetry_config()

    # Telemetry init
    session = SessionContext()
    log_file = setup_logging(tel_config, session) if tel_config.enabled else None

    transport: NetworkTransport | None = None
    if tel_config.enabled and tel_config.network_sync_enabled and tel_config.network_path:
        transport = NetworkTransport(tel_config.network_path)

    if tel_config.enabled:
        log_event("zabra.app", "app_start", **session.as_dict())

    app = ZabraApp(
        configs={
            "inventor_export": inventor_config,
            "inventor_simplify": simplify_config,
            "inventor_drawing": drawing_config,
        },
        session=session,
        telemetry_config=tel_config,
        log_file=log_file,
        transport=transport,
    )

    try:
        app.run()
    finally:
        if tel_config.enabled:
            log_event("zabra.app", "app_stop")
        if transport and log_file:
            transport.enqueue(log_file)
            transport.stop()
        save_config(inventor_config)
        save_simplify_config(simplify_config)
        save_drawing_config(drawing_config)
        save_telemetry_config(tel_config)
