"""
The start menu: pure state and render, plus the real ``Application`` driven by
synthetic keys (same technique and escape sequences as ``test_tui_app.py``).
"""

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from modules.tui.app import build_menu_application
from modules.tui.menu_render import render_menu
from modules.tui.menu_state import APONTAR, ATUALIZAR, CRIAR, ITEMS, MenuState

UP, DOWN, RIGHT, LEFT = "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"
ENTER, SPACE, TAB, ESCAPE, CTRL_C, BACKSPACE = "\r", " ", "\t", "\x1b\x1b", "\x03", "\x08"


def _run(keys: str):
    with create_pipe_input() as pipe:
        pipe.send_text(keys)
        return build_menu_application(MenuState(), input=pipe, output=DummyOutput()).run()


# ------------------------------------------------------------------- state


def test_the_menu_lists_the_three_operations_and_closes_the_last():
    assert [item.key for item in ITEMS] == [APONTAR, ATUALIZAR, CRIAR]
    assert [item.closed for item in ITEMS] == [False, False, True]


def test_it_opens_on_apontar():
    assert MenuState().activate() == APONTAR


def test_navigation_wraps_in_both_directions():
    state = MenuState()
    state.move_prev()
    assert state.activate() == CRIAR
    state.move_next()
    assert state.activate() == APONTAR


# ------------------------------------------------------------------ render


def test_the_render_marks_the_focused_item_and_says_the_last_one_is_closed():
    state = MenuState()
    text = render_menu(state)
    marked = [line for line in text.splitlines() if line.startswith("> ")]
    assert len(marked) == 1 and "Apontar" in marked[0]
    assert "Criar OSI" in text and "INTERDITADO" in text
    state.move_prev()
    assert "Criar OSI" in [line for line in render_menu(state).splitlines() if line.startswith("> ")][0]


def test_the_render_footer_names_what_enter_does_and_is_ascii():
    text = render_menu(MenuState())
    assert "[ENTER] / [ESPACO]" in text
    assert "ABRE a operacao em foco" in text
    assert text.isascii()


# --------------------------------------------------------------- the screen


def test_enter_opens_the_focused_operation():
    assert _run(ENTER) == APONTAR
    assert _run(DOWN + ENTER) == ATUALIZAR


def test_space_does_exactly_what_enter_does():
    assert _run(SPACE) == APONTAR
    assert _run(DOWN + SPACE) == ATUALIZAR


def test_tab_and_up_move_the_focus_too():
    assert _run(TAB + ENTER) == ATUALIZAR
    assert _run(UP + ENTER) == CRIAR


def test_the_closed_item_is_still_returned_so_the_caller_can_explain():
    assert _run(DOWN + DOWN + ENTER) == CRIAR


def test_left_and_right_do_nothing_in_a_menu():
    assert _run(RIGHT + LEFT + ENTER) == APONTAR


@pytest.mark.parametrize("key", [ESCAPE, CTRL_C, BACKSPACE])
def test_escape_ctrl_c_and_backspace_all_close_the_menu(key):
    assert _run(key) is None
