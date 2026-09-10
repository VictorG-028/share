"""
Orchestrator / entry point.

Responsibilities (the only place that wires generation to browser-driving):
  1. load the trusted history,
  2. pick a strategy via the factory (default: static),
  3. generate the appointment value(s) ONCE,
  4. refuse anything that is not in the past (SSG accepts only past days --
     not even today -- and ``force`` does not bypass that),
  5. skip weekends and Brazilian holidays by default (override with force=True),
  6. optionally hand the *same* generated values to a BrowserController.

Keeping generation and browser-driving apart is deliberate: the numbers are
produced here once and handed to whichever controller drives the site.

The CLI defaults to generating and printing -- nothing opens a browser and
nothing is written until asked. ``--fill`` types without saving; ``--save``
writes, and asks for confirmation first.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

from models.appointment import Appointment
from modules.history.loader import _load_history, append_appointment
from modules.holiday.service import is_holiday
from modules.strategy import DEFAULT_STRATEGY, StrategyType, get_strategy

WEEKEND = {5, 6}  # Saturday, Sunday

#: Exit codes. 2 means "nothing to do", which is not a failure: a skipped
#: holiday should not make a scheduled run look broken.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOTHING_TO_DO = 2

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")
_YES = {"s", "sim", "y", "yes"}


def parse_day(text: str) -> date:
    """Parse ``AAAA-MM-DD`` or ``DD/MM/AAAA``."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"data invalida: {text!r} (use AAAA-MM-DD ou DD/MM/AAAA)"
    )


def skip_reason(target_day: date, *, force: bool = False) -> str | None:
    """
    Why ``target_day`` cannot be punched, or ``None`` if it can.

    The past-only rule comes first and is unconditional: SSG rejects the
    current day and anything later, so ``force`` cannot lift it. ``force``
    exists only for a weekend or holiday you were actually asked to work.
    """
    if target_day >= date.today():
        return "nao esta no passado -- o SSG so aceita dias passados, nem hoje"
    if force:
        return None
    if target_day.weekday() in WEEKEND:
        return "fim de semana (use --force)"
    if is_holiday(target_day):
        return "feriado (use --force)"
    return None


def run(
    target_day: date,
    strategy_type: StrategyType = DEFAULT_STRATEGY,
    *,
    force: bool = False,
) -> Appointment | None:
    """
    Generate the appointment for ``target_day``, or ``None`` if it is skipped.

    Skipping is reported on stdout and is not an error -- see
    :func:`skip_reason` for what disqualifies a day.
    """
    reason = skip_reason(target_day, force=force)
    if reason:
        print(f"{target_day.isoformat()}: {reason}. Nao gerei nada.")
        return None

    history = _load_history()
    strategy = get_strategy(strategy_type, history=history)
    appointment = strategy.generate_for(target_day)
    print(f"[{strategy_type.value}] {target_day.isoformat()}: {appointment}")
    return appointment


def run_week(
    any_day_in_week: date,
    strategy_type: StrategyType = DEFAULT_STRATEGY,
    *,
    force: bool = False,
) -> list[Appointment]:
    """
    Generate Monday..Friday of the week containing ``any_day_in_week``.

    Goes through the strategy's own ``generate_week`` rather than looping over
    :func:`run`, because ``NaturalRandomStrategy`` keeps the days of a week
    unique from each other (Rule 4) -- generating them one at a time would
    throw that away. Ineligible days are dropped afterwards.
    """
    history = _load_history()
    strategy = get_strategy(strategy_type, history=history)

    kept: list[Appointment] = []
    for appointment in strategy.generate_week(any_day_in_week):
        reason = skip_reason(appointment.day, force=force)
        if reason:
            print(f"{appointment.day.isoformat()}: {reason}. Pulei.")
            continue
        print(f"[{strategy_type.value}] {appointment.day.isoformat()}: {appointment}")
        kept.append(appointment)
    return kept


def _describe(appointment: Appointment, osi: str) -> str:
    # The whole label, not a number: the day's list also carries the OSIs the
    # manager opened for the team, and "OSI 82695" on the confirmation line
    # would no longer tell you which project you are about to book.
    return (
        f"  {appointment.day.strftime('%d/%m/%Y')}  "
        f"{appointment.entry_time:%H:%M} / {appointment.lunch_start:%H:%M} / "
        f"{appointment.lunch_end:%H:%M} / {appointment.exit_time:%H:%M}\n"
        f"  {osi}"
    )


def _confirm(appointment: Appointment, osi: str, *, assume_yes: bool) -> bool:
    """Ask before writing. Refuses rather than guessing when there is no tty."""
    print("Vou GRAVAR no SSG:")
    print(_describe(appointment, osi))
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("Sem terminal interativo para confirmar. Use --yes se e isso mesmo.")
        return False
    return input("Confirma a gravacao? [s/N] ").strip().lower() in _YES


def punch(
    appointments: list[Appointment],
    *,
    save: bool = False,
    osi: str | None = None,
    port: int | None = None,
    assume_yes: bool = False,
) -> int:
    """
    Replay generated values in the browser. Returns an exit code.

    With ``save=False`` this types and verifies without writing anything -- and
    then only one day makes sense, because moving to the next day re-filters
    the screen and discards what was typed.
    """
    # Imported lazily so the generate-and-print path never touches the browser
    # stack (nor its websocket dependency).
    from modules.browser.browsers import DEFAULT_PORT, BrowserNotFound
    from modules.browser.cdp import CdpError
    from modules.browser.ssg_controller import (
        SsgController,
        SsgError,
        SsgLoginRequired,
    )
    from modules.osi_catalog import load_last_used, save_last_used

    if not appointments:
        return EXIT_NOTHING_TO_DO
    if not save and len(appointments) > 1:
        print(
            "--fill sem --save so faz sentido para um dia: filtrar o dia seguinte "
            "descarta o preenchimento do anterior. Use --save, ou um dia por vez."
        )
        return EXIT_ERROR

    # No built-in default: the OSI list is day-dependent and a constant in the
    # code goes stale the month it is written. What you punched last is the
    # only honest guess; with nothing to fall back on, refuse instead.
    selector = osi or load_last_used()
    if not selector:
        print(
            "Nenhuma OSI escolhida e nenhuma usada antes. "
            "Rode refresh-osi-list e escolha na tela, ou passe --osi."
        )
        return EXIT_ERROR

    controller = SsgController(osi=selector, port=port or DEFAULT_PORT)
    written = 0
    try:
        controller.open()
        print(f"browser: {controller.browser_name}")
        for appointment in appointments:
            controller.fill_appointment(appointment)
            print(f"{appointment.day.isoformat()}: preenchido e conferido.")
            if not save:
                continue
            if not _confirm(appointment, controller.osi_selected or selector, assume_yes=assume_yes):
                print(f"{appointment.day.isoformat()}: nao gravei.")
                continue
            controller.save_day(appointment)
            written += 1
            # Only a punch that really landed goes into the history, so Rule 4
            # keeps checking against what was actually recorded.
            append_appointment(appointment)
            save_last_used(controller.osi_selected or selector)
            print(f"{appointment.day.isoformat()}: GRAVADO e confirmado no servidor.")
    except SsgLoginRequired as error:
        print(f"Login necessario: {error}")
        return EXIT_ERROR
    except (BrowserNotFound, SsgError, CdpError) as error:
        print(f"Erro: {error}")
        return EXIT_ERROR
    finally:
        controller.close()

    if save and not written:
        return EXIT_NOTHING_TO_DO
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auto-appointment",
        description=(
            "Gera horarios de apontamento e, se pedido, os digita no SSG. "
            "Por padrao apenas imprime: nada abre o browser e nada e gravado."
        ),
    )
    parser.add_argument(
        "--day",
        "-d",
        type=parse_day,
        help="dia alvo (AAAA-MM-DD ou DD/MM/AAAA). Padrao: ontem.",
    )
    parser.add_argument(
        "--week",
        action="store_true",
        help="segunda a sexta da semana de --day, pulando o que nao for passado",
    )
    parser.add_argument(
        "--strategy",
        choices=[s.value for s in StrategyType],
        default=DEFAULT_STRATEGY.value,
        help="como gerar os horarios (padrao: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="apontar mesmo em fim de semana ou feriado (NAO libera hoje/futuro)",
    )
    parser.add_argument(
        "--fill",
        action="store_true",
        help="abrir o browser, preencher e conferir -- sem gravar",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="gravar no SSG (implica --fill; pergunta antes)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="nao perguntar antes de gravar",
    )
    parser.add_argument(
        "--osi",
        help=(
            "qual OSI apontar: o rotulo como o site mostra, ou qualquer trecho "
            "que case com uma linha so (o numero, ex. 82695, ainda serve). "
            "Sem isso, usa a ultima que voce gravou"
        ),
    )
    parser.add_argument("--port", type=int, help="porta do CDP (padrao: 9222)")
    parser.add_argument(
        "--refresh-osi-list",
        action="store_true",
        help=(
            "abre o SSG, LE (nao grava) a lista de OSI e atualiza o cache "
            "local; ignora as outras flags"
        ),
    )
    parser.add_argument(
        "--register-new-osi",
        action="store_true",
        help=(
            "cadastra uma OSI nova, perguntando projeto e atividade e "
            "confirmando antes de gravar; ignora as outras flags "
            "(o comando register-new-osi tem as opcoes nao interativas)"
        ),
    )
    return parser


def refresh_osi_list(*, port: int | None = None) -> int:
    """Read-only: refresh the local OSI catalog cache from the live site."""
    # Imported lazily, same reasoning as punch()'s browser-stack imports.
    from modules.browser.browsers import DEFAULT_PORT, BrowserNotFound
    from modules.browser.cdp import CdpError
    from modules.browser.ssg_controller import SsgError, SsgLoginRequired
    from modules.osi_catalog import refresh_catalog, save_catalog

    try:
        entries = refresh_catalog(port=port or DEFAULT_PORT)
    except SsgLoginRequired as error:
        print(f"Login necessario: {error}")
        return EXIT_ERROR
    except (BrowserNotFound, SsgError, CdpError) as error:
        print(f"Erro: {error}")
        return EXIT_ERROR
    save_catalog(entries)
    print(f"OSI: {len(entries)} entradas gravadas em cache.")
    return EXIT_OK if entries else EXIT_NOTHING_TO_DO


def cli(argv: list[str] | None = None) -> int:
    """Entry point. Returns an exit code; see EXIT_* above."""
    if argv is None and len(sys.argv) == 1 and sys.stdin.isatty():
        from modules.tui import run_tui

        built = run_tui()
        if built is None:
            return EXIT_NOTHING_TO_DO
        return cli(built)

    args = build_parser().parse_args(argv)
    if args.refresh_osi_list:
        return refresh_osi_list(port=args.port)
    if args.register_new_osi:
        from register_new_osi import run as register_new_osi

        return register_new_osi(port=args.port)
    target_day = args.day or (date.today() - timedelta(days=1))
    strategy_type = StrategyType(args.strategy)

    if args.week:
        appointments = run_week(target_day, strategy_type, force=args.force)
    else:
        appointment = run(target_day, strategy_type, force=args.force)
        appointments = [appointment] if appointment else []

    if not appointments:
        return EXIT_NOTHING_TO_DO
    if not (args.fill or args.save):
        return EXIT_OK

    return punch(
        appointments,
        save=args.save,
        osi=args.osi,
        port=args.port,
        assume_yes=args.yes,
    )


if __name__ == "__main__":
    # A frozen build launched by double-click gets its own console, which
    # Windows closes the instant the process exits -- a one-line dry-run (or
    # an unhandled exception) then reads as a crash. Pause before closing,
    # but only when stdin is a real console: an unattended run (Task
    # Scheduler, a pipe) must not hang waiting for a key that never comes.
    try:
        exit_code = cli()
    except Exception:
        import traceback

        traceback.print_exc()
        exit_code = 1
    if getattr(sys, "frozen", False) and sys.stdin.isatty():
        try:
            input("\nPressione Enter para fechar...")
        except EOFError:
            pass
    sys.exit(exit_code)
