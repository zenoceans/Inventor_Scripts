"""CLI entry point for inventor_simplify_tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from inventor_simplify_tool.config import load_simplify_config
from inventor_simplify_tool.models import SimplifyRow
from inventor_simplify_tool.orchestrator import SimplifyOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch import and simplify STEP files via Autodesk Inventor."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        metavar="DIR",
        help="Directory containing .step / .stp files to process",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Output directory for simplified .ipt files (defaults to --input-dir)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir

    step_files = [
        str(p) for p in Path(input_dir).iterdir() if p.suffix.lower() in {".step", ".stp"}
    ]
    if not step_files:
        print(f"No .step/.stp files found in: {input_dir}")
        sys.exit(1)

    rows = [
        SimplifyRow(
            step_path=f,
            output_filename=Path(f).stem,
            output_folder=output_dir,
        )
        for f in step_files
    ]

    config = load_simplify_config()

    def log(msg: str) -> None:
        print(msg)

    orchestrator = SimplifyOrchestrator(config, rows, log_callback=log)
    summary = orchestrator.run()

    sys.exit(1 if summary.failed else 0)
