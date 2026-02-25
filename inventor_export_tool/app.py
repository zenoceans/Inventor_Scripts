"""Application entry point — loads config and launches GUI."""

from __future__ import annotations

import sys

from inventor_export_tool.config import load_config, save_config
from inventor_export_tool.gui import ExportToolGUI


def main() -> None:
    if sys.platform != "win32":
        print("This tool requires Windows (Inventor COM automation).")
        sys.exit(1)

    config = load_config()
    gui = ExportToolGUI(config)

    try:
        gui.run()
    finally:
        save_config(config)
