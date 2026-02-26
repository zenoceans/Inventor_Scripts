"""Zabra-Cadabra application entry point."""

from __future__ import annotations

import sys


def main() -> None:
    if sys.platform != "win32":
        print("Zabra-Cadabra requires Windows.")
        sys.exit(1)

    from inventor_export_tool.config import load_config, save_config
    from inventor_simplify_tool.config import load_simplify_config, save_simplify_config
    from zabra_cadabra.shell import ZabraApp

    inventor_config = load_config()
    simplify_config = load_simplify_config()
    app = ZabraApp(
        configs={"inventor_export": inventor_config, "inventor_simplify": simplify_config}
    )

    try:
        app.run()
    finally:
        save_config(inventor_config)
        save_simplify_config(simplify_config)
