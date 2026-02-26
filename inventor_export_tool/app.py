"""Application entry point — delegates to Zabra-Cadabra shell."""

from __future__ import annotations


def main() -> None:
    from zabra_cadabra.app import main as zabra_main

    zabra_main()
