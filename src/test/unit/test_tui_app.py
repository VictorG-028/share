"""
The only test file importing ``prompt_toolkit`` -- drives the real
``Application`` with synthetic key sequences via ``create_pipe_input()``, so
navigation/key-binding logic gets genuine coverage without a real terminal.

Standard xterm escape sequences: Up ``\\x1b[A``, Down ``\\x1b[B``,
Right ``\\x1b[C``, Left ``\\x1b[D``, Enter ``\\r``, Ctrl-C ``\\x03``.
A lone Escape is ambiguous with the start of one of those sequences, so
tests that need a plain Escape send it twice (prompt_toolkit resolves the
first as a real Escape once a second byte confirms it isn't a sequence).
"""

from datetime import date

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import main
from modules.osi_catalog.entry import OsiEntry
from modules.tui.app import build_application
from modules.tui.state import DateCursor, FormState, OsiSpinner

PAST_WEEKDAY = date(2026, 5, 29)  # a Friday, comfortably in the past
SATURDAY = date(2026, 5, 30)

UP, DOWN, RIGHT, LEFT = "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"
ENTER, ESCAPE, CTRL_C = "\r", "\x1b\x1b", "\x03"
TAB, SPACE = "\t", " "
TO_OSI = RIGHT * 4  # day -> month -> year -> force -> osi row


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


def test_enter_from_a_valid_past_date_submits():
    state = _state(PAST_WEEKDAY)
    result = _run(state, ENTER)
    assert result == ["--day", "29/05/2026", "--osi", "OSI 82695", "--save", "--yes"]


def test_enter_on_todays_default_submits_when_forced():
    today = date.today()
    state = _state(today, force=True)
    result = _run(state, ENTER)
    assert result == [
        "--day", today.strftime("%d/%m/%Y"),
        "--force", "--osi", "OSI 82695", "--save", "--yes",
    ]


def test_left_from_osi_never_lands_on_force():
    state = _state(PAST_WEEKDAY)
    _run(state, RIGHT * 4 + LEFT * 5 + CTRL_C)
    assert (state.row, state.field) == (1, 0)  # osi row, never back to force


def test_force_unblocks_a_weekend_date_and_shows_in_argv():
    state = _state(SATURDAY)
    # move to Force (day -> month -> year -> force), toggle it on, then submit
    result = _run(state, RIGHT * 3 + UP + ENTER)
    assert state.date.force is True
    assert result is not None
    assert "--force" in result


def test_ctrl_c_cancels():
    state = _state(PAST_WEEKDAY)
    result = _run(state, CTRL_C)
    assert result is None


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


def test_space_on_the_osi_row_opens_the_list_and_space_chooses():
    state = _three_osi_state()
    _run(state, TO_OSI + SPACE + DOWN + SPACE + CTRL_C)
    assert state.osi.picking is False
    assert state.osi.current().label.startswith("coe tech - setembro")


def test_enter_on_the_osi_row_opens_the_list_instead_of_submitting():
    state = _three_osi_state()
    result = _run(state, TO_OSI + ENTER + CTRL_C)
    assert state.osi.picking is True
    assert result is None  # nothing was submitted


def test_tab_opens_the_list_and_tab_again_leaves_it_unchanged():
    state = _three_osi_state()
    _run(state, TO_OSI + TAB + DOWN + DOWN + TAB + CTRL_C)
    assert state.osi.picking is False
    assert state.osi.current().label.startswith("OSI 83270")


def test_escape_in_the_list_goes_back_without_choosing_and_keeps_the_form():
    state = _three_osi_state()
    result = _run(state, TO_OSI + SPACE + DOWN + ESCAPE + CTRL_C)
    assert state.osi.picking is False
    assert state.osi.current().label.startswith("OSI 83270")
    assert result is None


def test_choosing_in_the_list_is_what_the_submitted_argv_carries():
    state = _three_osi_state()
    # pick the second OSI, walk to the Salvar row, submit
    result = _run(state, TO_OSI + SPACE + DOWN + ENTER + RIGHT + ENTER)
    assert result is not None
    assert result[2:4] == ["--osi", "coe tech - setembro - 2026 | Fulano - 2"]


def test_ctrl_c_leaves_even_with_the_list_open():
    state = _three_osi_state()
    result = _run(state, TO_OSI + SPACE + CTRL_C)
    assert result is None
