from datetime import date

import pytest

import main
from modules.osi_catalog.entry import OsiEntry
from modules.tui.render import RED, YELLOW, render_text
from modules.tui.state import DateCursor, FormState, OsiSpinner

PAST_WEEKDAY = date(2026, 5, 29)
SATURDAY = date(2026, 5, 30)


@pytest.fixture(autouse=True)
def _no_holidays(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)


def _state(d: date, *, is_fallback: bool = False) -> FormState:
    entry = OsiEntry(number="82695", label="OSI 82695")
    return FormState(
        date=DateCursor(day=d.day, month=d.month, year=d.year),
        osi=OsiSpinner(entries=[entry], is_fallback=is_fallback),
    )


def test_clean_date_has_no_color_codes():
    text = render_text(_state(PAST_WEEKDAY))
    assert RED not in text
    assert YELLOW not in text


def test_today_is_red():
    text = render_text(_state(date.today()))
    assert RED in text


def test_weekend_without_force_is_yellow():
    text = render_text(_state(SATURDAY))
    assert YELLOW in text


def test_fallback_hint_present_only_when_fallback():
    with_fallback = render_text(_state(PAST_WEEKDAY, is_fallback=True))
    without_fallback = render_text(_state(PAST_WEEKDAY, is_fallback=False))
    assert "rode --refresh-osi-list" in with_fallback
    assert "rode --refresh-osi-list" not in without_fallback


def test_focused_segment_is_marked():
    state = _state(PAST_WEEKDAY)
    state.row, state.field = 0, 1  # month
    text = render_text(state)
    assert "\033[7m" in text  # reverse-video marker present
