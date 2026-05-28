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
        help="Output directory (defaults to config value if omitted)",
    )
    parser.add_argument(
        "--formats",
        default="step",
        metavar="FORMATS",
        help="Comma-separated export formats: step, pdf, dwg (default: step)",
    )
    parser.add_argument(
        "--preset",
        metavar="NAME",
        default=None,
        help="Name of a naming preset from config. Defaults to the active preset.",
    )
    parser.add_argument(
        "--exclude-prefixes",
        metavar="PREFIXES",
        default=None,
        help=(
            "Comma-separated filename prefixes to exclude "
            "(case-insensitive, e.g. 'DIN,ISO,2,3'). Overrides the config value."
        ),
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

    if args.preset is not None:
        preset_names = [p.name for p in config.naming_presets]
        if args.preset not in preset_names:
            print(
                f"ERROR: Preset '{args.preset}' not found. Available: {', '.join(preset_names)}",
                file=sys.stderr,
            )
            sys.exit(1)
        config.active_preset_name = args.preset

    if args.exclude_prefixes is not None:
        config.excluded_filename_prefixes = [
            p.strip() for p in args.exclude_prefixes.split(",") if p.strip()
        ]

    def log(msg: str) -> None:
        print(msg)

    from inventor_api._com_threading import com_thread_scope
    from inventor_api.exceptions import InventorError

    try:
        with com_thread_scope():
            orchestrator = ExportOrchestrator(config, log_callback=log)
            summary = orchestrator.scan()
            results = orchestrator.export(summary)
    except InventorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    failed = sum(1 for r in results if not r.success)
    sys.exit(1 if failed else 0)
