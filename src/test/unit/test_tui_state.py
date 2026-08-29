import calendar
from datetime import date

import pytest

import main
from modules.tui.state import DateCursor, FormState, OsiSpinner, load_osi_spinner
from modules.osi_catalog.entry import OsiEntry

SATURDAY = date(2026, 5, 30)
FRIDAY = date(2026, 5, 29)  # a week comfortably in the past


@pytest.fixture(autouse=True)
def _no_holidays(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)


def _cursor(d: date, *, force: bool = False) -> DateCursor:
    return DateCursor(day=d.day, month=d.month, year=d.year, force=force)


# ------------------------------------------------------------- bump_day


def test_bump_day_rolls_over_the_month_boundary():
    cursor = _cursor(date(2026, 1, 31))
    cursor.bump_day(1)
    assert (cursor.year, cursor.month, cursor.day) == (2026, 2, 1)


def test_bump_day_rolls_over_the_year_boundary():
    cursor = _cursor(date(2026, 12, 31))
    cursor.bump_day(1)
    assert (cursor.year, cursor.month, cursor.day) == (2027, 1, 1)


def test_bump_day_negative_rolls_backward():
    cursor = _cursor(date(2026, 3, 1))
    cursor.bump_day(-1)
    assert (cursor.year, cursor.month, cursor.day) == (2026, 2, 28)


# --------------------------------------------------------- bump_month/year


def test_bump_month_clamps_day_to_the_new_months_length():
    cursor = _cursor(date(2026, 1, 31))
    cursor.bump_month(1)
    assert cursor.month == 2
    assert cursor.day == (29 if calendar.isleap(2026) else 28)
    assert calendar.isleap(2026) is False  # 2026 is not a leap year
    assert cursor.day == 28


def test_bump_month_clamps_in_a_leap_year():
    cursor = _cursor(date(2028, 1, 31))
    cursor.bump_month(1)
    assert calendar.isleap(2028) is True
    assert cursor.day == 29


def test_bump_month_wraps_the_year_forward():
    cursor = _cursor(date(2026, 12, 15))
    cursor.bump_month(1)
    assert (cursor.year, cursor.month) == (2027, 1)


def test_bump_year_clamps_feb_29_on_a_non_leap_year():
    cursor = _cursor(date(2028, 2, 29))
    cursor.bump_year(1)
    assert calendar.isleap(2029) is False
    assert (cursor.year, cursor.month, cursor.day) == (2029, 2, 28)


def test_toggle_force_flips():
    cursor = _cursor(FRIDAY)
    assert cursor.force is False
    cursor.toggle_force()
    assert cursor.force is True
    cursor.toggle_force()
    assert cursor.force is False


# ------------------------------------------------------------------ status


def test_status_today_is_blocked_red_even_with_force():
    cursor = _cursor(date.today(), force=True)
    status = cursor.status()
    assert status.blocked is True
    assert status.color == "red"


def test_status_future_is_blocked_red_even_with_force():
    from datetime import timedelta

    cursor = _cursor(date.today() + timedelta(days=1), force=True)
    status = cursor.status()
    assert status.blocked is True
    assert status.color == "red"


def test_status_past_weekday_is_clean():
    cursor = _cursor(FRIDAY)
    status = cursor.status()
    assert status.blocked is False
    assert status.color is None


def test_status_past_weekend_is_yellow_and_blocked_without_force():
    cursor = _cursor(SATURDAY, force=False)
    status = cursor.status()
    assert status.blocked is True
    assert status.color == "yellow"


def test_status_past_weekend_is_unblocked_with_force():
    cursor = _cursor(SATURDAY, force=True)
    status = cursor.status()
    assert status.blocked is False


def test_status_past_holiday_is_yellow_and_blocked_without_force(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: True)
    cursor = _cursor(FRIDAY, force=False)
    status = cursor.status()
    assert status.blocked is True
    assert status.color == "yellow"


def test_status_past_holiday_is_unblocked_with_force(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: True)
    cursor = _cursor(FRIDAY, force=True)
    status = cursor.status()
    assert status.blocked is False


# --------------------------------------------------------------- OsiSpinner


def test_osi_spinner_bump_wraps_both_directions():
    entries = [OsiEntry(number="1", label="a"), OsiEntry(number="2", label="b")]
    spinner = OsiSpinner(entries=entries)
    spinner.bump(-1)
    assert spinner.current().number == "2"
    spinner.bump(1)
    assert spinner.current().number == "1"


def test_load_osi_spinner_falls_back_when_catalog_is_empty(monkeypatch):
    import modules.osi_catalog as osi_catalog

    monkeypatch.setattr(osi_catalog, "load_catalog", lambda: [])
    monkeypatch.setattr(osi_catalog, "load_last_used", lambda: None)
    spinner = load_osi_spinner()
    assert spinner.is_fallback is True
    assert len(spinner.entries) == 1


def test_load_osi_spinner_defaults_to_last_used(monkeypatch):
    import modules.osi_catalog as osi_catalog

    entries = [
        OsiEntry(number="1", label="a"),
        OsiEntry(number="2", label="b"),
        OsiEntry(number="3", label="c"),
    ]
    monkeypatch.setattr(osi_catalog, "load_catalog", lambda: entries)
    monkeypatch.setattr(osi_catalog, "load_last_used", lambda: "2")
    spinner = load_osi_spinner()
    assert spinner.is_fallback is False
    assert spinner.current().number == "2"


def test_load_osi_spinner_defaults_to_zero_when_last_used_not_found(monkeypatch):
    import modules.osi_catalog as osi_catalog

    entries = [OsiEntry(number="1", label="a"), OsiEntry(number="2", label="b")]
    monkeypatch.setattr(osi_catalog, "load_catalog", lambda: entries)
    monkeypatch.setattr(osi_catalog, "load_last_used", lambda: "does-not-exist")
    spinner = load_osi_spinner()
    assert spinner.current().number == "1"
