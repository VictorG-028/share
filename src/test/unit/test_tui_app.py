"""
The only test file besides the menu/refresh ones importing ``prompt_toolkit``
-- drives the real ``Application`` with synthetic key sequences via
``create_pipe_input()``, so key-binding logic gets genuine coverage without a
real terminal.

Standard xterm escape sequences: Up ``\\x1b[A``, Down ``\\x1b[B``,
Right ``\\x1b[C``, Left ``\\x1b[D``, Shift-Tab ``\\x1b[Z``, Enter ``\\r``,
Ctrl-C ``\\x03``, Backspace ``\\x08``. A lone Escape is ambiguous with the
start of one of those sequences, so tests that need a plain Escape send it
twice (prompt_toolkit resolves the first as a real Escape once a second byte
confirms it isn't a sequence).
"""

from datetime import date, timedelta

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import main
from modules.osi_catalog.entry import OsiEntry
from modules.tui.app import build_application
from modules.tui.state import DateCursor, FormState, OsiSpinner

PAST_WEEKDAY = date(2026, 5, 29)  # a Friday, comfortably in the past
SATURDAY = date(2026, 5, 30)

UP, DOWN, RIGHT, LEFT, SHIFT_TAB = "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D", "\x1b[Z"
ENTER, ESCAPE, CTRL_C, BACKSPACE = "\r", "\x1b\x1b", "\x03", "\x08"
TAB, SPACE = "\t", " "

# The form is one flat list: day, month, year, force, osi, action, run.
TO_FORCE = DOWN * 3
TO_OSI = DOWN * 4
TO_ACTION = DOWN * 5
TO_RUN = DOWN * 6


@pytest.fixture(autouse=True)
def _no_holidays(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)


def _state(d: date, *, force: bool = False) -> FormState:
    return FormState(
        date=DateCursor(day=d.day, month=d.month, year=d.year, force=force),
        osi=OsiSpinner(entries=[OsiEntry(number="82695", label="OSI 82695")]),
    )


def _run(state: FormState, keys: str):
    with create_pipe_input() as pipe_input:
        app = build_application(state, input=pipe_input, output=DummyOutput())
        pipe_input.send_text(keys)
        return app.run()


# ------------------------------------------------------ Enter only executes last


def test_enter_on_the_last_button_executes_and_by_default_only_fills():
    result = _run(_state(PAST_WEEKDAY), TO_RUN + ENTER)
    assert result == ["--day", "29/05/2026", "--osi", "OSI 82695", "--fill"]


def test_space_does_exactly_what_enter_does():
    assert _run(_state(PAST_WEEKDAY), TO_RUN + SPACE) == _run(_state(PAST_WEEKDAY), TO_RUN + ENTER)


def test_enter_anywhere_else_never_executes():
    state = _state(PAST_WEEKDAY)
    # One press on every line but the button: day, month, year, force, osi
    # (which opens the list -- the second Enter chooses and closes it), action.
    # Then leave: nothing was ever submitted.
    keys = (
        ENTER + DOWN + ENTER + DOWN + ENTER + DOWN + ENTER + DOWN
        + ENTER + ENTER + DOWN + ENTER + CTRL_C
    )
    assert _run(state, keys) is None
    assert state.focus_name() == "action"


def test_enter_on_a_value_moves_it_forward_and_stays_on_the_form():
    state = _state(PAST_WEEKDAY)
    result = _run(state, ENTER + CTRL_C)  # day, forward
    assert result is None
    assert state.date.as_date() == date(2026, 5, 30)


def test_enter_on_the_action_line_switches_to_saving_and_the_button_follows():
    state = _state(PAST_WEEKDAY)
    result = _run(state, TO_ACTION + ENTER + DOWN + ENTER)
    assert state.save is True
    assert result == ["--day", "29/05/2026", "--osi", "OSI 82695", "--save", "--yes"]


def test_the_button_on_a_blocked_day_stays_on_the_form():
    state = _state(date.today() + timedelta(days=1))
    assert _run(state, TO_RUN + ENTER + CTRL_C) is None  # Enter did not submit
    assert state.focus_name() == "run"


def test_enter_on_todays_default_executes_when_forced():
    today = date.today()
    result = _run(_state(today, force=True), TO_RUN + ENTER)
    assert result == [
        "--day", today.strftime("%d/%m/%Y"),
        "--force", "--osi", "OSI 82695", "--fill",
    ]


# ---------------------------------------------------------------- the arrows


def test_down_and_up_change_the_line_and_never_a_value():
    state = _state(PAST_WEEKDAY)
    _run(state, DOWN + DOWN + UP + CTRL_C)
    assert state.focus_name() == "month"
    assert state.date.as_date() == PAST_WEEKDAY


def test_tab_and_shift_tab_walk_the_lines_like_down_and_up():
    state = _state(PAST_WEEKDAY)
    _run(state, TAB + TAB + SHIFT_TAB + CTRL_C)
    assert state.focus_name() == "month"


def test_up_from_the_first_line_wraps_to_the_button():
    state = _state(PAST_WEEKDAY)
    _run(state, UP + CTRL_C)
    assert state.focus_name() == "run"


def test_right_and_left_change_the_focused_value_in_opposite_directions():
    state = _state(PAST_WEEKDAY)
    _run(state, RIGHT + RIGHT + LEFT + CTRL_C)
    assert state.date.as_date() == date(2026, 5, 30)
    assert state.focus_name() == "day"  # the focus did not move


def test_the_old_w_and_s_shortcuts_are_gone():
    state = _state(PAST_WEEKDAY)
    _run(state, "w" + "s" + CTRL_C)
    assert state.date.as_date() == PAST_WEEKDAY


def test_force_unblocks_a_weekend_date_and_shows_in_argv():
    state = _state(SATURDAY)
    result = _run(state, TO_FORCE + RIGHT + DOWN + DOWN + DOWN + ENTER)
    assert state.date.force is True
    assert result is not None
    assert "--force" in result


# -------------------------------------------------------------------- cancel


@pytest.mark.parametrize("key", [CTRL_C, ESCAPE, BACKSPACE])
def test_ctrl_c_escape_and_backspace_all_cancel_the_form(key):
    assert _run(_state(PAST_WEEKDAY), key) is None


@pytest.mark.parametrize("key", [CTRL_C, ESCAPE, BACKSPACE])
def test_cancelling_from_the_button_does_not_execute(key):
    assert _run(_state(PAST_WEEKDAY), TO_RUN + key) is None


# --------------------------------------------------------------- OSI overlay


def _three_osi_state(d: date = PAST_WEEKDAY) -> FormState:
    state = _state(d)
    state.osi = OsiSpinner(
        entries=[
            OsiEntry.from_label("OSI 83270 | P | A - 1"),
            OsiEntry.from_label("coe tech - setembro - 2026 | Fulano - 2"),
            OsiEntry.from_label("coe tech - agosto - 2026 | Fulano - 3"),
        ]
    )
    return state


def test_space_on_the_osi_line_opens_the_list_and_space_chooses():
    state = _three_osi_state()
    _run(state, TO_OSI + SPACE + DOWN + SPACE + CTRL_C)
    assert state.osi.picking is False
    assert state.osi.current().label.startswith("coe tech - setembro")


def test_enter_on_the_osi_line_opens_the_list_instead_of_executing():
    state = _three_osi_state()
    result = _run(state, TO_OSI + ENTER + CTRL_C)
    assert state.osi.picking is True
    assert result is None


def test_choosing_goes_back_to_the_form_on_the_osi_line():
    state = _three_osi_state()
    _run(state, TO_OSI + ENTER + DOWN + ENTER + CTRL_C)
    assert state.osi.picking is False
    assert state.focus_name() == "osi"


def test_up_and_down_in_the_list_do_not_move_the_forms_focus():
    state = _three_osi_state()
    _run(state, TO_OSI + SPACE + DOWN + DOWN + UP + CTRL_C)
    assert state.focus_name() == "osi"
    assert state.osi.pick_index == 1


@pytest.mark.parametrize("key", [ESCAPE, BACKSPACE])
def test_escape_and_backspace_in_the_list_go_back_without_choosing_and_keep_the_form(key):
    state = _three_osi_state()
    result = _run(state, TO_OSI + SPACE + DOWN + key + CTRL_C)
    assert state.osi.picking is False
    assert state.osi.current().label.startswith("OSI 83270")
    assert result is None


def test_left_and_right_change_the_osi_without_opening_the_list():
    state = _three_osi_state()
    _run(state, TO_OSI + RIGHT + CTRL_C)
    assert state.osi.picking is False
    assert state.osi.current().label.startswith("coe tech - setembro")
    _run(state, LEFT + CTRL_C)
    assert state.osi.current().label.startswith("OSI 83270")


def test_choosing_in_the_list_is_what_the_executed_argv_carries():
    state = _three_osi_state()
    # pick the second OSI, then walk down to the button and execute
    result = _run(state, TO_OSI + SPACE + DOWN + ENTER + DOWN + DOWN + ENTER)
    assert result is not None
    assert result[2:4] == ["--osi", "coe tech - setembro - 2026 | Fulano - 2"]


def test_ctrl_c_leaves_even_with_the_list_open():
    state = _three_osi_state()
    assert _run(state, TO_OSI + SPACE + CTRL_C) is None
