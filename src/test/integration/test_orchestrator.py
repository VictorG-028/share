"""
Orchestrator day-gating (past-only / weekend / holiday / force).

No network involved.
"""

from datetime import date, timedelta

import main
from modules.strategy.static.generator import static_times

SATURDAY = date(2026, 5, 30)
FRIDAY = date(2026, 5, 29)


def test_skips_weekend_without_force():
    # Weekend check returns before any holiday/network lookup.
    assert main.run(SATURDAY) is None


def test_force_punches_weekend_with_spare_set():
    appt = main.run(SATURDAY, force=True)
    assert appt is not None
    assert appt.day == SATURDAY
    # Saturday uses the spare set #6.
    assert (appt.entry_time, appt.lunch_start, appt.lunch_end, appt.exit_time) == static_times(6)


def test_skips_holiday(monkeypatch):
    # Force the holiday predicate so no network is touched.
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: True)
    assert main.run(FRIDAY) is None


def test_punches_ordinary_weekday(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)
    appt = main.run(FRIDAY)
    assert appt is not None
    assert appt.day == FRIDAY


# SSG only accepts days already in the past -- not the current day, and
# certainly not the future. The rule is hard: force does not lift it.


def test_refuses_today_even_with_force(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)
    assert main.run(date.today(), force=True) is None


def test_refuses_the_future_even_with_force(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)
    assert main.run(date.today() + timedelta(days=1), force=True) is None


def test_yesterday_is_allowed(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)
    yesterday = date.today() - timedelta(days=1)
    assert main.run(yesterday, force=True) is not None
