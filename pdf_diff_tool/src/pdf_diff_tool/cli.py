"""CLI entry point for pdf_diff_tool."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pdf_diff_tool.config import load_config
from pdf_diff_tool.differ import diff_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two PDF files and generate a visual diff PDF."
    )
    parser.add_argument("old_pdf", type=Path, help="Path to the old (previous revision) PDF")
    parser.add_argument("new_pdf", type=Path, help="Path to the new (current revision) PDF")
    parser.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="Output path for the diff PDF (default: alongside new PDF)",
    )
    parser.add_argument(
        "--dpi", type=int, default=None, help="Render resolution in DPI (default: 150)"
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Don't open the diff PDF after generation"
    )
    args = parser.parse_args()

    if not args.old_pdf.exists():
        print(f"Error: file not found: {args.old_pdf}", file=sys.stderr)
        sys.exit(1)
    if not args.new_pdf.exists():
        print(f"Error: file not found: {args.new_pdf}", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    dpi = args.dpi or config.dpi

    if args.output:
        output_path = args.output
    else:
        output_path = args.new_pdf.parent / f"{args.old_pdf.stem}_vs_{args.new_pdf.stem}_diff.pdf"

    def log_progress(current: int, total: int) -> None:
        print(f"Processing page {current}/{total}...")

    try:
        result = diff_pdfs(args.old_pdf, args.new_pdf, output_path, dpi=dpi, progress_callback=log_progress)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if result.has_differences:
        print(f"Differences found. Diff saved to: {result.output_path}")
    else:
        print(f"No differences found. Diff saved to: {result.output_path}")

    if not args.no_open and config.open_after_diff:
        os.startfile(str(result.output_path))
