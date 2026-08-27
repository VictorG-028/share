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
from modules.history.loader import DEFAULT_HISTORY_FILE, _load_history
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

    history = _load_history(DEFAULT_HISTORY_FILE)
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
    history = _load_history(DEFAULT_HISTORY_FILE)
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
    return (
        f"  {appointment.day.strftime('%d/%m/%Y')}  "
        f"{appointment.entry_time:%H:%M} / {appointment.lunch_start:%H:%M} / "
        f"{appointment.lunch_end:%H:%M} / {appointment.exit_time:%H:%M}   OSI {osi}"
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
        DEFAULT_OSI_NUMBER,
        SsgController,
        SsgError,
        SsgLoginRequired,
    )

    if not appointments:
        return EXIT_NOTHING_TO_DO
    if not save and len(appointments) > 1:
        print(
            "--fill sem --save so faz sentido para um dia: filtrar o dia seguinte "
            "descarta o preenchimento do anterior. Use --save, ou um dia por vez."
        )
        return EXIT_ERROR

    controller = SsgController(
        osi_number=osi or DEFAULT_OSI_NUMBER,
        port=port or DEFAULT_PORT,
    )
    written = 0
    try:
        controller.open()
        print(f"browser: {controller.browser_name}")
        for appointment in appointments:
            controller.fill_appointment(appointment)
            print(f"{appointment.day.isoformat()}: preenchido e conferido.")
            if not save:
                continue
            if not _confirm(appointment, controller.osi_number, assume_yes=assume_yes):
                print(f"{appointment.day.isoformat()}: nao gravei.")
                continue
            controller.save_day(appointment)
            written += 1
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
    parser.add_argument("--osi", help="numero da OSI a apontar")
    parser.add_argument("--port", type=int, help="porta do CDP (padrao: 9222)")
    return parser


def cli(argv: list[str] | None = None) -> int:
    """Entry point. Returns an exit code; see EXIT_* above."""
    args = build_parser().parse_args(argv)
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
    sys.exit(cli())
