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


def _focus(state: FormState, name: str) -> FormState:
    state.focus = ROWS.index(name)
    return state


# ------------------------------------------------------------ navigation


def test_the_form_is_one_flat_list_in_reading_order():
    assert ROWS == ("day", "month", "year", "force", "osi", "action", "run")


def test_down_walks_every_line_and_wraps_to_the_top():
    state = _state()
    visited = [state.focus_name()]
    for _ in ROWS:
        state.move_next()
        visited.append(state.focus_name())
    assert visited[: len(ROWS)] == list(ROWS)
    assert visited[-1] == ROWS[0]


def test_up_goes_back_one_line_and_wraps_to_the_button():
    state = _state()
    state.move_prev()
    assert state.focus_name() == "run"
    state.move_prev()
    assert state.focus_name() == "action"


def test_moving_between_lines_never_changes_a_value():
    state = _state()
    before = (state.date.day, state.date.month, state.date.year, state.date.force, state.save)
    for _ in range(2 * len(ROWS)):
        state.move_next()
    for _ in range(len(ROWS)):
        state.move_prev()
    after = (state.date.day, state.date.month, state.date.year, state.date.force, state.save)
    assert before == after


# ------------------------------------------------------------- bump_value


def test_right_and_left_change_the_focused_value_in_opposite_directions():
    state = _focus(_state(), "day")
    state.bump_value(+1)
    assert state.date.as_date() == PAST_WEEKDAY + timedelta(days=1)
    state.bump_value(-1)
    assert state.date.as_date() == PAST_WEEKDAY


def test_force_and_action_toggle():
    state = _focus(_state(), "force")
    assert state.date.force is False
    state.bump_value(+1)
    assert state.date.force is True

    state = _focus(_state(), "action")
    assert state.save is False  # the safe default: fill, never save
    state.bump_value(+1)
    assert state.save is True
    state.bump_value(-1)
    assert state.save is False


def test_the_button_has_no_value_to_change():
    state = _focus(_state(), "run")
    before = (state.date.as_date(), state.date.force, state.save)
    state.bump_value(+1)
    state.bump_value(-1)
    assert (state.date.as_date(), state.date.force, state.save) == before


# --------------------------------------------------------------- activate


def test_enter_on_a_value_moves_it_forward_like_right_does():
    forward, enter = _focus(_state(), "month"), _focus(_state(), "month")
    forward.bump_value(+1)
    assert enter.activate() is None
    assert enter.date.as_date() == forward.date.as_date()


def test_enter_on_the_osi_line_opens_the_list_and_does_not_execute():
    state = _focus(_state(), "osi")
    assert state.activate() is None
    assert state.osi.picking is True


def test_enter_executes_only_on_the_last_button():
    for name in ROWS[:-1]:
        state = _focus(_state(), name)
        assert state.activate() is None, name
    result = _focus(_state(), "run").activate()
    assert result is not None
    assert "--day" in result


def test_the_button_follows_the_action_line():
    state = _state()
    assert _focus(state, "run").activate()[-1] == "--fill"
    state.save = True
    assert _focus(state, "run").activate()[-2:] == ["--save", "--yes"]


def test_the_button_does_nothing_while_the_form_is_blocked():
    state = _focus(_state(date.today() + timedelta(days=1)), "run")
    assert state.activate() is None  # the future is always blocked


# --------------------------------------------------------------- submit


def test_try_submit_returns_none_when_blocked():
    state = _state(date.today() + timedelta(days=1))
    assert state.try_submit() is None


def test_try_submit_returns_argv_when_valid():
    result = _state().try_submit()
    assert result is not None
    assert "--day" in result
