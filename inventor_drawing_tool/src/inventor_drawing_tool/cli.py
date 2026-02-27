"""CLI entry point for the drawing release tool."""

from __future__ import annotations

import argparse
import sys
from threading import Event

from inventor_api._com_threading import com_thread_scope

from inventor_drawing_tool.config import load_drawing_config
from inventor_drawing_tool.models import DrawingStatus, RevisionData
from inventor_drawing_tool.orchestrator import DrawingReleaseOrchestrator


def main() -> None:
    """Run the drawing release tool from the command line."""
    parser = argparse.ArgumentParser(
        prog="inventor-drawing",
        description="Batch drawing creation and revision release for Inventor assemblies.",
    )

    # Required revision arguments
    parser.add_argument("--rev", required=True, help="Revision number (e.g. 'A', '01')")
    parser.add_argument("--made-by", required=True, help="Name of the person making the revision")
    parser.add_argument("--approved-by", required=True, help="Name of the approver")

    # Optional revision arguments
    parser.add_argument("--description", default="", help="Revision description")

    # Drawing creation options
    parser.add_argument(
        "--template",
        metavar="PATH",
        help="Drawing template (.idw) path. Overrides config.",
    )
    parser.add_argument(
        "--no-create",
        action="store_true",
        help="Skip drawing creation for parts without drawings (revision write only)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        help="Default view scale for new drawings. Overrides config.",
    )

    # Scan options
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help="Max assembly traversal depth (default: unlimited)",
    )
    parser.add_argument(
        "--include-asm",
        action="store_true",
        help="Include sub-assemblies in scan (default: parts only)",
    )
    parser.add_argument(
        "--include-suppressed",
        action="store_true",
        help="Include suppressed components in scan",
    )
    parser.add_argument(
        "--include-content-center",
        action="store_true",
        help="Include Content Center parts in scan",
    )

    # Processing options
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't auto-save after writing revision",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Don't close drawings after processing",
    )

    args = parser.parse_args()

    # Load config and apply CLI overrides
    config = load_drawing_config()
    if args.template:
        config.template_path = args.template
    if args.no_create:
        config.auto_create_drawings = False
    if args.scale is not None:
        config.default_scale = args.scale
    if args.depth is not None:
        config.max_depth = args.depth
    if args.include_asm:
        config.include_subassemblies = True
    if args.include_suppressed:
        config.include_suppressed = True
    if args.include_content_center:
        config.include_content_center = True
    if args.no_save:
        config.save_after_revision = False
    if args.keep_open:
        config.close_after_processing = False

    revision_data = RevisionData(
        rev_number=args.rev,
        rev_description=args.description,
        made_by=args.made_by,
        approved_by=args.approved_by,
    )

    def log_callback(msg: str) -> None:
        print(msg)

    def progress_callback(current: int, total: int) -> None:
        if total > 0:
            pct = current * 100 // total
            print(f"  [{current}/{total}] {pct}%", end="\r")

    with com_thread_scope():
        orchestrator = DrawingReleaseOrchestrator(
            config=config,
            revision_data=revision_data,
            progress_callback=progress_callback,
            log_callback=log_callback,
        )

        # Scan
        scan_result = orchestrator.scan()

        if not scan_result.items:
            print("No components found in the active assembly.")
            sys.exit(0)

        # Print review table
        print()
        print(f"{'Part Name':<30} {'Type':<10} {'Status':<10} {'Drawing'}")
        print("-" * 80)
        for item in scan_result.items:
            drawing_display = item.drawing_path or "(will create)"
            print(
                f"{item.part_name:<30} {item.document_type:<10} "
                f"{item.drawing_status.value:<10} {drawing_display}"
            )
        print("-" * 80)
        print(
            f"Total: {scan_result.total_parts} | "
            f"With drawings: {scan_result.parts_with_drawings} | "
            f"Without: {scan_result.parts_without_drawings}"
        )
        print()

        # Count items that need creation but auto-create is off
        needs_create = sum(
            1 for i in scan_result.items if i.drawing_status == DrawingStatus.NEEDS_CREATION
        )
        if needs_create > 0 and not config.auto_create_drawings:
            print(
                f"Note: {needs_create} items need drawings but --no-create is set. "
                "They will be skipped."
            )

        # Confirm
        answer = input("Proceed with release? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

        # Execute
        print()
        summary = orchestrator.execute(scan_result.items, cancel_event=Event())
        print()
        print(
            f"Release complete: {summary.created} created, "
            f"{summary.revised} revised, {summary.failed} failed"
        )

        if orchestrator.last_log_path:
            print(f"Log: {orchestrator.last_log_path}")

        if summary.failed > 0:
            sys.exit(1)
