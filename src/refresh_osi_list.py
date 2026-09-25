"""
Standalone entry point for refreshing the local OSI catalog cache.

Packaged as its own executable (separate from auto-appointment.exe) so this
read-only, occasional maintenance action -- "open the SSG, read the OSI list,
update the cache" -- is a double-click instead of typing --refresh-osi-list
into the main CLI. Mirrors main.py's own __main__ block: same frozen-console
pause-before-close and same top-level exception handling.

Double-clicked, it has no command line to type options into, so a no-argument
run on a real console opens the same screen the appointment form uses. The
options themselves are defined once in ``main.add_refresh_arguments`` and
shared, so this executable can never do more (or less) than
``auto-appointment --refresh-osi-list``.
"""

from __future__ import annotations

import argparse
import sys

from main import EXIT_ERROR, EXIT_NOTHING_TO_DO, add_refresh_arguments, refresh_osi_list


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="refresh-osi-list",
        description=(
            "Abre o SSG, LE (nao grava) a lista de OSI e atualiza o cache local."
        ),
    )
    parser.add_argument("--port", type=int, help="porta do CDP (padrao: 9222)")
    add_refresh_arguments(parser)
    return parser


def cli(argv: list[str] | None = None) -> int:
    # Same gate as main.cli, and for the same reason: the installed console
    # script's dunder-main is the stub's, not this module's, so a check inside
    # ``if __name__ == "__main__"`` would only ever fire for the frozen .exe.
    # Gating on ``argv is None`` also keeps ``cli([])`` meaning exactly "run
    # with every default", which is what the tests assert.
    if argv is None and len(sys.argv) == 1 and sys.stdin.isatty():
        from modules.tui import run_refresh_tui

        built = run_refresh_tui()
        if built is None:  # cancelled -- an empty list means "all defaults"
            return EXIT_NOTHING_TO_DO
        return cli(built)

    args = build_parser().parse_args(argv)
    return refresh_osi_list(
        port=args.port,
        include_holidays=args.incluir_feriado,
        include_weekends=args.incluir_fim_de_semana,
        source=args.fonte,
    )


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
