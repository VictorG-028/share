"""
CLI parsing, day selection and the guards around writing.

No browser and no network: the holiday predicate is patched where it is used.
Anything about "past" uses dates relative to today, so the tests keep meaning
as time passes.
"""

import argparse
import sys
from datetime import date, time, timedelta

import pytest

import main
import modules.tui as tui
from models.appointment import Appointment
from modules.strategy import StrategyType

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)

SATURDAY = date(2026, 5, 30)
FRIDAY = date(2026, 5, 29)  # a week comfortably in the past


@pytest.fixture(autouse=True)
def _no_holidays(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)


def _appointment(day: date = date(2026, 8, 26)) -> Appointment:
    return Appointment(
        day=day,
        entry_time=time(9, 3),
        lunch_start=time(12, 7),
        lunch_end=time(13, 8),
        exit_time=time(18, 4),
    )


# ------------------------------------------------------------------ parsing


def test_parse_day_accepts_iso():
    assert main.parse_day("2026-08-26") == date(2026, 8, 26)


def test_parse_day_accepts_brazilian_order():
    assert main.parse_day("26/08/2026") == date(2026, 8, 26)


def test_parse_day_rejects_garbage():
    with pytest.raises(argparse.ArgumentTypeError):
        main.parse_day("ontem")


# -------------------------------------------------------------------- gates


def test_today_is_eligible_when_forced():
    assert main.skip_reason(TODAY, force=True) is None


def test_future_is_never_eligible_not_even_forced():
    assert main.skip_reason(TOMORROW, force=True) is not None


def test_weekend_needs_force():
    assert main.skip_reason(SATURDAY) is not None
    assert main.skip_reason(SATURDAY, force=True) is None


def test_holiday_needs_force(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: True)
    assert main.skip_reason(FRIDAY) is not None
    assert main.skip_reason(FRIDAY, force=True) is None


# ---------------------------------------------------------------------- cli


def test_defaults_to_yesterday(monkeypatch):
    seen: list[date] = []
    monkeypatch.setattr(main, "run", lambda d, s, **kw: seen.append(d) or None)
    main.cli([])
    assert seen == [YESTERDAY]


def test_skipped_day_is_not_a_failure(monkeypatch):
    monkeypatch.setattr(main, "run", lambda d, s, **kw: None)
    assert main.cli(["--day", "2026-08-26"]) == main.EXIT_NOTHING_TO_DO


def test_without_fill_or_save_the_browser_is_never_touched(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("punch() nao deveria ser chamado")

    monkeypatch.setattr(main, "punch", _boom)
    assert main.cli(["--day", FRIDAY.isoformat()]) == main.EXIT_OK


# ------------------------------------------------------------- tui trigger


def test_tui_triggers_with_no_real_args_and_a_real_terminal(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["auto-appointment"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(tui, "run_tui", lambda: ["--day", FRIDAY.isoformat()])
    seen: list[date] = []
    monkeypatch.setattr(main, "run", lambda d, s, **kw: seen.append(d) or None)
    main.cli()
    assert seen == [FRIDAY]  # recursed into cli(built) with the TUI's argv


def test_tui_cancellation_is_nothing_to_do(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["auto-appointment"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(tui, "run_tui", lambda: None)
    assert main.cli() == main.EXIT_NOTHING_TO_DO


def test_tui_does_not_trigger_with_real_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["auto-appointment", "--day", FRIDAY.isoformat()])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def _boom():
        raise AssertionError("run_tui() nao deveria ser chamado com argv real")

    monkeypatch.setattr(tui, "run_tui", _boom)
    seen: list[date] = []
    monkeypatch.setattr(main, "run", lambda d, s, **kw: seen.append(d) or None)
    main.cli()
    assert seen == [FRIDAY]


def test_tui_does_not_trigger_without_a_real_terminal(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["auto-appointment"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    def _boom():
        raise AssertionError("run_tui() nao deveria ser chamado sem tty")

    monkeypatch.setattr(tui, "run_tui", _boom)
    seen: list[date] = []
    monkeypatch.setattr(main, "run", lambda d, s, **kw: seen.append(d) or None)
    main.cli()
    assert seen == [YESTERDAY]


def test_cli_of_empty_list_never_triggers_the_tui(monkeypatch):
    # The literal invariant: main.cli([]) must mean exactly what it means
    # today ("yesterday, dry mode"), regardless of real sys.argv/isatty --
    # see test_defaults_to_yesterday.
    monkeypatch.setattr(sys, "argv", ["auto-appointment"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def _boom():
        raise AssertionError("run_tui() nao deveria ser chamado para cli([])")

    monkeypatch.setattr(tui, "run_tui", _boom)
    seen: list[date] = []
    monkeypatch.setattr(main, "run", lambda d, s, **kw: seen.append(d) or None)
    main.cli([])
    assert seen == [YESTERDAY]


# ---------------------------------------------------------------------- week


def test_week_keeps_monday_to_friday_of_a_past_week():
    week = main.run_week(FRIDAY, StrategyType.STATIC)
    assert [a.day.weekday() for a in week] == [0, 1, 2, 3, 4]


def test_week_drops_days_after_today():
    # The current week always has days later than today that have not
    # happened yet -- those are dropped. Today itself is no longer dropped.
    for appointment in main.run_week(TODAY, StrategyType.STATIC):
        assert appointment.day <= TODAY


def test_week_goes_through_the_strategy_week_helper(monkeypatch):
    # NaturalRandomStrategy keeps a week's days unique from each other (Rule 4);
    # generating them one at a time would throw that away.
    calls: list[date] = []
    real = main.get_strategy

    def _spy(strategy_type, **kwargs):
        strategy = real(strategy_type, **kwargs)
        original = strategy.generate_week
        strategy.generate_week = lambda d: calls.append(d) or original(d)
        return strategy

    monkeypatch.setattr(main, "get_strategy", _spy)
    main.run_week(FRIDAY, StrategyType.STATIC)
    assert calls == [FRIDAY]


# ------------------------------------------------------------- write guards


def test_fill_without_save_refuses_more_than_one_day():
    # Filtering the next day re-renders the screen and discards what was typed.
    two = [_appointment(date(2026, 8, 24)), _appointment(date(2026, 8, 25))]
    assert main.punch(two, save=False) == main.EXIT_ERROR


def test_punch_with_nothing_to_do():
    assert main.punch([], save=True) == main.EXIT_NOTHING_TO_DO


def test_confirmation_declined_means_no_write(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert main._confirm(_appointment(), "82695", assume_yes=False) is False


def test_yes_skips_the_prompt():
    assert main._confirm(_appointment(), "82695", assume_yes=True) is True


def test_no_tty_refuses_instead_of_guessing(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main._confirm(_appointment(), "82695", assume_yes=False) is False


def test_punch_refuses_when_there_is_no_osi_to_use(monkeypatch, capsys):
    # No built-in default any more: the browser must not even open.
    import modules.osi_catalog as osi_catalog

    monkeypatch.setattr(osi_catalog, "load_last_used", lambda: None)
    assert main.punch([_appointment()], save=False) == main.EXIT_ERROR
    assert "refresh-osi-list" in capsys.readouterr().out


def test_the_confirmation_shows_the_whole_label_not_just_a_number():
    label = "coe tech - setembro - 2026 | Walber Hugo da Silva - 427465"
    assert label in main._describe(_appointment(), label)


# ------------------------------------------------------- refresh the catalog


def test_both_entry_points_share_the_same_refresh_options():
    import refresh_osi_list as dedicated

    for parser in (main.build_parser(), dedicated.build_parser()):
        args = parser.parse_args(
            ["--fonte", "ambas", "--incluir-feriado", "--incluir-fim-de-semana"]
        )
        assert (args.fonte, args.incluir_feriado, args.incluir_fim_de_semana) == (
            "ambas",
            True,
            True,
        )


def test_refresh_defaults_to_the_fast_source_and_workdays_only():
    args = main.build_parser().parse_args(["--refresh-osi-list"])
    assert args.fonte == "apontamento"
    assert not args.incluir_feriado and not args.incluir_fim_de_semana


def test_refresh_passes_the_options_through_and_ignores_the_punching_flags(monkeypatch):
    seen = {}

    def _fake(**kwargs):
        seen.update(kwargs)
        return main.EXIT_OK

    monkeypatch.setattr(main, "refresh_osi_list", lambda **kw: _fake(**kw))
    assert main.cli(["--refresh-osi-list", "--fonte", "listagem", "--save", "--week"]) == main.EXIT_OK
    assert seen["source"] == "listagem"
    assert seen["include_holidays"] is False
    # --save and --week belong to punching and must not leak into a read-only
    # action; the refresh call takes no such argument at all.
    assert set(seen) == {"port", "source", "include_holidays", "include_weekends"}


def test_an_unknown_source_is_refused_by_the_parser():
    with pytest.raises(SystemExit):
        main.build_parser().parse_args(["--refresh-osi-list", "--fonte", "inventada"])
