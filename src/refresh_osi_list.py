"""
Standalone entry point for refreshing the local OSI catalog cache.

Packaged as its own executable (separate from auto-appointment.exe) so this
read-only, occasional maintenance action -- "open the SSG, read the OSI list,
update the cache" -- is a double-click instead of typing --refresh-osi-list
into the main CLI. Mirrors main.py's own __main__ block: same frozen-console
pause-before-close and same top-level exception handling.
"""

from __future__ import annotations

import argparse
import sys

from main import EXIT_ERROR, refresh_osi_list


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="refresh-osi-list",
        description=(
            "Abre o SSG, LE (nao grava) a lista de OSI e atualiza o cache local."
        ),
    )
    parser.add_argument("--port", type=int, help="porta do CDP (padrao: 9222)")
    return parser


def cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return refresh_osi_list(port=args.port)


if __name__ == "__main__":
    try:
        exit_code = cli()
    except Exception:
        import traceback

        traceback.print_exc()
        exit_code = EXIT_ERROR
    if getattr(sys, "frozen", False) and sys.stdin.isatty():
        try:
            input("\nPressione Enter para fechar...")
        except EOFError:
            pass
    sys.exit(exit_code)
