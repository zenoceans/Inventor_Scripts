"""CLI entry point for inventor_export_tool."""

from __future__ import annotations

import argparse
import sys

from inventor_export_tool.config import load_config
from inventor_export_tool.orchestrator import ExportOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-export Inventor assemblies to STEP, DWG, and/or PDF."
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Output directory (defaults to --input-dir if omitted)",
    )
    parser.add_argument(
        "--formats",
        default="step",
        metavar="FORMATS",
        help="Comma-separated export formats: step, pdf, dwg (default: step)",
    )
    args = parser.parse_args()

    formats = {f.strip().lower() for f in args.formats.split(",")}
    valid = {"step", "pdf", "dwg"}
    unknown = formats - valid
    if unknown:
        print(
            f"ERROR: Unknown format(s): {', '.join(sorted(unknown))}. Choose from: step, pdf, dwg"
        )
        sys.exit(1)

    config = load_config()
    if args.output_dir:
        config.output_folder = args.output_dir

    config.export_step = "step" in formats
    config.export_dwg = "dwg" in formats
    config.export_pdf = "pdf" in formats

    def log(msg: str) -> None:
        print(msg)

    orchestrator = ExportOrchestrator(config, log_callback=log)
    summary = orchestrator.scan()
    results = orchestrator.export(summary)

    failed = sum(1 for r in results if not r.success)
    sys.exit(1 if failed else 0)
