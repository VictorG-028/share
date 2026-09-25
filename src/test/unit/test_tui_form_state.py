from datetime import date, timedelta

import pytest

import main
from modules.osi_catalog.entry import OsiEntry
from modules.tui.state import ROWS, DateCursor, FormState, OsiSpinner

PAST_WEEKDAY = date(2026, 5, 29)  # a Friday, comfortably in the past


@pytest.fixture(autouse=True)
def _no_holidays(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)


def _state(d: date = PAST_WEEKDAY) -> FormState:
    return FormState(
        date=DateCursor(day=d.day, month=d.month, year=d.year),
        osi=OsiSpinner(entries=[OsiEntry(number="82695", label="OSI 82695")]),
    )


# ------------------------------------------------------------ navigation


def test_move_right_walks_through_every_field_and_wraps_to_row_zero():
    state = _state()
    visited = [(state.row, state.field)]
    for _ in range(sum(len(row) for row in ROWS)):
        state.move_right()
        visited.append((state.row, state.field))
    # after visiting every field, one more Right returns to the very start
    assert visited[0] == (0, 0)
    assert visited[-1] == (0, 0)
    # the day/month/year/force row, then the osi row, then the save row
    assert visited[1] == (0, 1)  # month
    assert visited[4] == (1, 0)  # osi (row wrap after force)
    assert visited[5] == (2, 0)  # save (row wrap after osi)


def test_move_left_never_changes_row():
    state = _state()
    state.row, state.field = 1, 0  # osi row
    state.move_left()
    assert state.row == 1
    assert state.field == 0
    # repeated left from osi never lands back on force (previous row)
    state.move_left()
    state.move_left()
    assert state.row == 1


def test_move_left_stops_at_the_first_field_of_the_row():
    state = _state()
    state.row, state.field = 0, 2  # year
    state.move_left()
    assert state.field == 1  # month
    state.move_left()
    assert state.field == 0  # day
    state.move_left()
    assert state.field == 0  # stays


# ------------------------------------------------------------- bump_value


def test_bump_value_dispatches_to_the_focused_field():
    state = _state()
    state.row, state.field = 0, 0  # day
    before = state.date.day
    state.bump_value(1)
    assert state.date.day != before or state.date.month != PAST_WEEKDAY.month

    state.row, state.field = 0, 3  # force
    assert state.date.force is False
    state.bump_value(1)
    assert state.date.force is True

    state.row, state.field = 2, 0  # save
    assert state.save is True
    state.bump_value(1)
    assert state.save is False


# --------------------------------------------------------------- submit


def test_try_submit_returns_none_when_blocked_regardless_of_focus():
    future = date.today() + timedelta(days=1)
    state = _state(future)  # the future is always blocked
    for row in range(len(ROWS)):
        state.row = row
        assert state.try_submit() is None


def test_try_submit_returns_argv_when_valid():
    state = _state()  # a clean past weekday
    result = state.try_submit()
    assert result is not None
    assert "--day" in result
