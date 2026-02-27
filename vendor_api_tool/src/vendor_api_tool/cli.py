"""CLI entry point for the vendor API tool."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from vendor_api_tool.config import load_vendor_api_config
from vendor_api_tool.models import ComponentResult

DEFAULT_TEST_MPNS = ["3044168", "LM358DR", "1-104257-0", "2200484", "STM32F103C8T6"]

# Column widths for output table
_COL = {
    "source": 8,
    "mpn": 16,
    "manufacturer": 17,
    "description": 30,
    "weight": 10,
    "datasheet": 40,
}

_HEADER = (
    f"{'Source':<{_COL['source']}} | "
    f"{'MPN':<{_COL['mpn']}} | "
    f"{'Manufacturer':<{_COL['manufacturer']}} | "
    f"{'Description':<{_COL['description']}} | "
    f"{'Weight (g)':<{_COL['weight']}} | "
    f"Datasheet"
)
_SEPARATOR = "-" * (
    _COL["source"] + _COL["mpn"] + _COL["manufacturer"] + _COL["description"] + _COL["weight"] + 60
)


def _trunc(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: width - 1] + "\u2026"


def _format_row(result: ComponentResult) -> str:
    weight = f"{result.weight_grams:.2f}" if result.weight_grams is not None else "N/A"
    return (
        f"{_trunc(result.source, _COL['source']):<{_COL['source']}} | "
        f"{_trunc(result.mpn, _COL['mpn']):<{_COL['mpn']}} | "
        f"{_trunc(result.manufacturer, _COL['manufacturer']):<{_COL['manufacturer']}} | "
        f"{_trunc(result.description, _COL['description']):<{_COL['description']}} | "
        f"{weight:<{_COL['weight']}} | "
        f"{result.datasheet_url}"
    )


def _print_table(results: list[ComponentResult]) -> None:
    print(_HEADER)
    print(_SEPARATOR)
    for r in results:
        print(_format_row(r))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vendor-api",
        description="Look up component data from Nexar and DigiKey APIs.",
    )
    parser.add_argument(
        "mpns",
        nargs="*",
        default=None,
        metavar="MPN",
        help="One or more manufacturer part numbers to look up.",
    )
    parser.add_argument(
        "--nexar-only",
        action="store_true",
        help="Query Nexar only (skip DigiKey).",
    )
    parser.add_argument(
        "--digikey-only",
        action="store_true",
        help="Query DigiKey only (skip Nexar).",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip datasheet PDF weight lookup.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        metavar="N",
        help="Maximum Nexar results per MPN (default: 3).",
    )
    args = parser.parse_args()

    mpns: list[str] = args.mpns if args.mpns else DEFAULT_TEST_MPNS

    use_nexar = not args.digikey_only
    use_digikey = not args.nexar_only

    config = load_vendor_api_config()

    has_nexar = bool(config.nexar_client_id and config.nexar_client_secret)
    has_digikey = bool(config.digikey_client_id and config.digikey_client_secret)

    if use_nexar and not has_nexar:
        print("WARNING: Nexar credentials not configured — skipping Nexar queries.")
    if use_digikey and not has_digikey:
        print("WARNING: DigiKey credentials not configured — skipping DigiKey queries.")

    all_results: list[ComponentResult] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        nexar_client = None
        digikey_client = None

        try:
            if use_nexar and has_nexar:
                from vendor_api_tool.nexar import NexarClient

                nexar_client = NexarClient(config.nexar_client_id, config.nexar_client_secret)

            if use_digikey and has_digikey:
                from vendor_api_tool.digikey import DigiKeyClient

                digikey_client = DigiKeyClient(
                    config.digikey_client_id, config.digikey_client_secret
                )

            for mpn in mpns:
                mpn_results: list[ComponentResult] = []

                if nexar_client is not None:
                    try:
                        nexar_results = nexar_client.search_mpn(mpn, limit=args.limit)
                        mpn_results.extend(nexar_results)
                    except Exception as exc:
                        print(f"ERROR: Nexar query failed for {mpn!r}: {exc}")

                if digikey_client is not None:
                    try:
                        dk_result = digikey_client.search_mpn(mpn)
                        if dk_result is not None:
                            mpn_results.append(dk_result)
                    except Exception as exc:
                        print(f"ERROR: DigiKey query failed for {mpn!r}: {exc}")

                if not args.skip_pdf:
                    from vendor_api_tool.datasheet import lookup_weight_from_datasheet

                    for result in mpn_results:
                        if result.datasheet_url and result.weight_grams is None:
                            try:
                                weight = lookup_weight_from_datasheet(
                                    result.datasheet_url, tmp_path
                                )
                                if weight is not None:
                                    result.weight_grams = weight
                            except Exception as exc:
                                print(
                                    f"ERROR: PDF lookup failed for {result.mpn!r} "
                                    f"({result.source}): {exc}"
                                )

                all_results.extend(mpn_results)

        finally:
            if nexar_client is not None:
                try:
                    nexar_client.close()
                except Exception:
                    pass
            if digikey_client is not None:
                try:
                    digikey_client.close()
                except Exception:
                    pass

    if all_results:
        _print_table(all_results)
    else:
        print("No results returned.")
