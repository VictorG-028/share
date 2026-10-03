"""
The refresh screen: pure state and render, plus the real ``Application``
driven by synthetic keys (same technique and escape sequences as
``test_tui_app.py``).
"""

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import main
from modules.osi_catalog import SOURCE_BOTH, SOURCE_LISTING, SOURCE_TIMESHEET
from modules.tui.app import build_refresh_application
from modules.tui.refresh_render import BUTTON, render_refresh
from modules.tui.refresh_state import ROWS, RefreshFormState, build_refresh_argv

UP, DOWN, RIGHT, LEFT = "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"
ENTER, ESCAPE, CTRL_C, BACKSPACE = "\r", "\x1b\x1b", "\x03", "\x08"
SPACE = " "

# fonte, feriado, fim_de_semana, run
TO_RUN = DOWN * 3


def _run(state: RefreshFormState, keys: str):
    with create_pipe_input() as pipe:
        pipe.send_text(keys)
        return build_refresh_application(state, input=pipe, output=DummyOutput()).run()


def _focus(state: RefreshFormState, name: str) -> RefreshFormState:
    state.focus = ROWS.index(name)
    return state


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


def test_each_toggle_answers_only_on_its_own_line():
    state = RefreshFormState.initial()
    state.move_next()  # onto "feriado"
    state.bump_value(+1)
    assert state.include_holidays and not state.include_weekends
    state.move_next()  # onto "fim de semana"
    state.bump_value(+1)
    assert state.include_holidays and state.include_weekends


def test_navigation_is_one_flat_list_that_wraps_both_ways():
    state = RefreshFormState.initial()
    assert [state.focus_name()] + [
        (state.move_next(), state.focus_name())[1] for _ in range(len(ROWS))
    ] == [*ROWS, ROWS[0]]
    state.move_prev()
    assert state.focus_name() == "run"


def test_moving_between_lines_never_changes_a_value():
    state = RefreshFormState.initial()
    for _ in range(2 * len(ROWS)):
        state.move_next()
    assert build_refresh_argv(state) == []


def test_activate_moves_a_value_forward_and_executes_only_on_the_button():
    state = RefreshFormState.initial()
    assert state.activate() is None  # fonte, forward
    assert state.source.current() != SOURCE_TIMESHEET
    assert _focus(state, "feriado").activate() is None
    assert state.include_holidays
    assert _focus(state, "run").activate() == ["--fonte", state.source.current(), "--incluir-feriado"]


def test_the_button_with_every_default_answers_an_empty_list_not_none():
    # [] means "all defaults" and is a real answer; None would mean "stay".
    assert _focus(RefreshFormState.initial(), "run").activate() == []


def test_argv_only_carries_what_differs_from_the_default():
    state = RefreshFormState.initial()
    state.source.index = list(state.source.options).index(SOURCE_BOTH)
    state.include_weekends = True
    assert build_refresh_argv(state) == ["--fonte", SOURCE_BOTH, "--incluir-fim-de-semana"]


def test_the_argv_it_builds_is_one_the_cli_accepts():
    state = RefreshFormState.initial()
    state.include_holidays = True
    state.include_weekends = True
    state.source.index = list(state.source.options).index(SOURCE_LISTING)
    argv = ["--refresh-osi-list", *build_refresh_argv(state)]
    args = main.build_parser().parse_args(argv)
    assert args.refresh_osi_list is True
    assert (args.fonte, args.incluir_feriado, args.incluir_fim_de_semana) == (
        SOURCE_LISTING,
        True,
        True,
    )


# ------------------------------------------------------------------ render


def test_the_render_shows_the_source_its_hint_and_both_toggles():
    text = render_refresh(RefreshFormState.initial())
    assert SOURCE_TIMESHEET in text
    assert "considerar feriado" in text and "considerar fim de semana" in text
    assert "[ ]" in text and "[X]" not in text
    # It must be obvious that this screen writes nothing to the site.
    assert "nada e gravado" in text
    assert BUTTON in text


def test_a_toggle_that_is_on_is_drawn_as_such():
    state = RefreshFormState.initial()
    state.include_weekends = True
    assert "[X] considerar fim de semana" in render_refresh(state)


def test_the_focused_line_has_the_marker_and_the_value_is_reverse_video():
    text = render_refresh(RefreshFormState.initial())
    assert "\033[7m" + SOURCE_TIMESHEET in text
    marked = [line for line in text.splitlines() if line.startswith("> ")]
    assert len(marked) == 1 and marked[0].startswith("> Fonte")


@pytest.mark.parametrize("name", ROWS)
def test_the_legend_is_set_apart_from_the_form_by_two_blank_lines(name):
    lines = render_refresh(_focus(RefreshFormState.initial(), name)).splitlines()
    first = next(i for i, line in enumerate(lines) if "[ENTER]" in line)
    assert lines[first - 2 : first] == ["", ""]
    assert lines[first - 3] != ""


def test_the_footer_follows_the_focus_and_the_whole_screen_is_ascii():
    state = RefreshFormState.initial()
    assert "MUDA o valor para frente" in render_refresh(state)
    assert "EXECUTA: LER a lista de OSI" in render_refresh(_focus(state, "run"))
    for name in ROWS:
        assert render_refresh(_focus(state, name)).isascii()


# --------------------------------------------------------------- the screen


def test_enter_on_the_first_line_does_not_execute_it_changes_the_source():
    state = RefreshFormState.initial()
    assert _run(state, ENTER + CTRL_C) is None
    assert state.source.current() != SOURCE_TIMESHEET


def test_enter_on_the_button_submits_the_defaults():
    assert _run(RefreshFormState.initial(), TO_RUN + ENTER) == []


def test_arrows_change_the_source_before_executing():
    result = _run(RefreshFormState.initial(), RIGHT + TO_RUN + ENTER)
    assert result == ["--fonte", SOURCE_LISTING]


def test_left_goes_the_other_way():
    result = _run(RefreshFormState.initial(), LEFT + TO_RUN + ENTER)
    assert result == ["--fonte", SOURCE_BOTH]


def test_space_toggles_the_line_under_the_cursor():
    # fonte -> feriado (toggle) -> fim_de_semana -> run
    result = _run(RefreshFormState.initial(), DOWN + SPACE + DOWN + DOWN + ENTER)
    assert result == ["--incluir-feriado"]


@pytest.mark.parametrize("key", [ESCAPE, CTRL_C, BACKSPACE])
def test_escape_ctrl_c_and_backspace_all_cancel(key):
    # None, not [] -- an empty argv means "run with every default".
    assert _run(RefreshFormState.initial(), key) is None


def test_the_screen_never_blocks_the_button():
    # Nothing on this form can be invalid, so the button always yields an argv.
    # fonte -> feriado -> fim_de_semana (toggle) -> run
    assert isinstance(_run(RefreshFormState.initial(), DOWN + DOWN + SPACE + DOWN + ENTER), list)
