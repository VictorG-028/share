"""
The refresh screen: pure state and render, plus the real ``Application``
driven by synthetic keys (same technique and escape sequences as
``test_tui_app.py``).
"""

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from modules.osi_catalog import SOURCE_BOTH, SOURCE_LISTING, SOURCE_TIMESHEET
from modules.tui.app import build_refresh_application
from modules.tui.refresh_render import render_refresh
from modules.tui.refresh_state import RefreshFormState, build_refresh_argv

UP, DOWN, RIGHT, LEFT = "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"
ENTER, ESCAPE, CTRL_C = "\r", "\x1b\x1b", "\x03"
SPACE = " "


def _run(state: RefreshFormState, keys: str):
    with create_pipe_input() as pipe:
        pipe.send_text(keys)
        return build_refresh_application(state, input=pipe, output=DummyOutput()).run()


# ------------------------------------------------------------------- state


def test_it_starts_on_the_normal_path_with_both_toggles_off():
    state = RefreshFormState.initial()
    assert state.source.current() == SOURCE_TIMESHEET
    assert not state.include_holidays and not state.include_weekends
    # The default run has nothing to say on the command line.
    assert build_refresh_argv(state) == []


def test_the_source_cycles_and_comes_back():
    state = RefreshFormState.initial()
    seen = []
    for _ in range(4):
        seen.append(state.source.current())
        state.bump_value(+1)
    assert seen[0] == seen[3] == SOURCE_TIMESHEET
    assert set(seen) == {SOURCE_TIMESHEET, SOURCE_LISTING, SOURCE_BOTH}


def test_each_toggle_answers_only_on_its_own_field():
    state = RefreshFormState.initial()
    state.move_right()  # off the source row, onto "feriado"
    state.bump_value(+1)
    assert state.include_holidays and not state.include_weekends
    state.move_right()  # onto "fim de semana"
    state.bump_value(+1)
    assert state.include_holidays and state.include_weekends


def test_navigation_wraps_forward_and_stops_going_back():
    state = RefreshFormState.initial()
    assert state.focus_name() == "fonte"
    state.move_right()
    assert state.focus_name() == "feriado"
    state.move_right()
    assert state.focus_name() == "fim_de_semana"
    state.move_right()  # wraps to the first row
    assert state.focus_name() == "fonte"
    state.move_left()  # Left never changes row
    assert state.focus_name() == "fonte"


def test_argv_only_carries_what_differs_from_the_default():
    state = RefreshFormState.initial()
    state.source.index = list(state.source.options).index(SOURCE_BOTH)
    state.include_weekends = True
    assert build_refresh_argv(state) == ["--fonte", SOURCE_BOTH, "--incluir-fim-de-semana"]


def test_the_argv_it_builds_is_one_the_cli_accepts():
    import refresh_osi_list

    state = RefreshFormState.initial()
    state.include_holidays = True
    state.include_weekends = True
    state.source.index = list(state.source.options).index(SOURCE_LISTING)
    args = refresh_osi_list.build_parser().parse_args(build_refresh_argv(state))
    assert (args.fonte, args.incluir_feriado, args.incluir_fim_de_semana) == (
        SOURCE_LISTING,
        True,
        True,
    )


# ------------------------------------------------------------------ render


def test_the_render_shows_the_source_its_hint_and_both_toggles():
    state = RefreshFormState.initial()
    text = render_refresh(state)
    assert SOURCE_TIMESHEET in text
    assert "considerar feriado" in text and "considerar fim de semana" in text
    assert "[ ]" in text and "[X]" not in text
    # It must be obvious that this screen writes nothing to the site.
    assert "nada e gravado" in text


def test_a_toggle_that_is_on_is_drawn_as_such():
    state = RefreshFormState.initial()
    state.include_weekends = True
    assert "[X] considerar fim de semana" in render_refresh(state)


def test_the_focused_field_is_highlighted():
    state = RefreshFormState.initial()
    assert "\033[7m" + SOURCE_TIMESHEET in render_refresh(state)


# --------------------------------------------------------------- the screen


def test_enter_submits_the_defaults():
    assert _run(RefreshFormState.initial(), ENTER) == []


def test_arrows_change_the_source_before_submitting():
    result = _run(RefreshFormState.initial(), UP + ENTER)
    assert result == ["--fonte", SOURCE_LISTING]


def test_space_toggles_the_field_under_the_cursor():
    result = _run(RefreshFormState.initial(), RIGHT + SPACE + ENTER)
    assert result == ["--incluir-feriado"]


def test_escape_and_ctrl_c_both_cancel():
    # None, not [] -- an empty argv means "run with every default".
    assert _run(RefreshFormState.initial(), ESCAPE) is None
    assert _run(RefreshFormState.initial(), CTRL_C) is None


@pytest.mark.parametrize("keys", [RIGHT + RIGHT + SPACE + ENTER, DOWN + ENTER])
def test_the_screen_never_blocks_a_submission(keys):
    # Nothing on this form can be invalid, so Enter always produces an argv.
    assert isinstance(_run(RefreshFormState.initial(), keys), list)
