from datetime import date, timedelta

import pytest

import main
from modules.osi_catalog.entry import OsiEntry
from modules.tui.render import (
    BUTTON_FILL,
    BUTTON_SAVE,
    RED,
    YELLOW,
    render_text,
)
from modules.tui.state import ROWS, DateCursor, FormState, OsiSpinner

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


def _focus(state: FormState, name: str) -> FormState:
    state.focus = ROWS.index(name)
    return state


def _marked(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("> ")]


def test_clean_date_has_no_color_codes():
    text = render_text(_state(PAST_WEEKDAY))
    assert RED not in text
    assert YELLOW not in text


def test_today_is_no_longer_red():
    text = render_text(_state(date.today()))
    assert RED not in text


def test_weekend_without_force_is_yellow():
    text = render_text(_state(SATURDAY))
    assert YELLOW in text


def test_a_blocked_day_is_reported_once_next_to_the_button():
    text = render_text(_state(date.today() + timedelta(days=1)))
    assert "Bloqueado:" in text
    # The reason is not repeated under the date as well.
    assert text.count("Bloqueado:") == 1


def test_today_keeps_its_heads_up_under_the_date_and_is_not_blocked():
    state = _state(date.today())
    state.date.force = True  # today may be a weekend; force is what unblocks that
    text = render_text(state)
    assert "hoje:" in text
    assert "Bloqueado" not in text


def test_fallback_hint_present_only_when_fallback():
    with_fallback = render_text(_state(PAST_WEEKDAY, is_fallback=True))
    without_fallback = render_text(_state(PAST_WEEKDAY, is_fallback=False))
    assert "Atualizar lista de OSI" in with_fallback
    assert "Atualizar lista de OSI" not in without_fallback


# ------------------------------------------------------------- one per line


def test_every_field_is_on_its_own_line():
    text = render_text(_state(PAST_WEEKDAY))
    for label in ("Dia", "Mes", "Ano", "Force", "OSI", "Acao"):
        assert sum(line.lstrip("> ").startswith(label) for line in text.splitlines()) == 1


def test_exactly_one_line_carries_the_focus_marker_and_it_follows_the_focus():
    state = _state(PAST_WEEKDAY)
    for name, label in (("month", "Mes"), ("force", "Force"), ("action", "Acao")):
        marked = _marked(render_text(_focus(state, name)))
        assert len(marked) == 1
        assert marked[0].startswith(f"> {label}")


def test_the_focused_value_is_also_reverse_video():
    text = render_text(_focus(_state(PAST_WEEKDAY), "month"))
    assert "\033[7m05\033[0m" in text


# ------------------------------------------------- the action and the button


def test_the_default_action_only_fills_and_the_button_says_so():
    text = render_text(_state(PAST_WEEKDAY))
    assert "So preencher (nao grava)" in text
    assert BUTTON_FILL in text
    assert BUTTON_SAVE not in text


def test_choosing_to_save_renames_the_button_and_paints_it_red():
    state = _state(PAST_WEEKDAY)
    state.save = True
    text = render_text(state)
    assert "GRAVAR no SSG" in text
    assert BUTTON_SAVE in text
    assert BUTTON_FILL not in text
    assert f"{RED}{BUTTON_SAVE}" in text


# ------------------------------------------------------------------ footer


def _blank_lines_above_the_legend(text: str) -> int:
    lines = text.splitlines()
    first = next(i for i, line in enumerate(lines) if "[ENTER]" in line)
    count = 0
    while first - 1 - count >= 0 and lines[first - 1 - count] == "":
        count += 1
    return count


@pytest.mark.parametrize("name", ROWS)
def test_the_key_legend_is_set_apart_from_the_form_by_two_blank_lines(name):
    # With one blank line the legend read as more fields of the form.
    assert _blank_lines_above_the_legend(render_text(_focus(_state(PAST_WEEKDAY), name))) == 2


def test_the_overlay_legend_is_set_apart_by_two_blank_lines_too():
    assert _blank_lines_above_the_legend(render_text(_picker(["a", "b"]))) == 2


@pytest.mark.parametrize(
    "name, expected",
    [
        ("day", "MUDA o valor para frente"),
        ("action", "MUDA o valor para frente"),
        ("osi", "ABRE a lista de OSIs"),
        ("run", "EXECUTA:"),
    ],
)
def test_the_footer_says_what_enter_does_on_the_focused_line(name, expected):
    text = render_text(_focus(_state(PAST_WEEKDAY), name))
    assert expected in text
    assert "[ENTER] / [ESPACO]" in text


def test_the_footer_on_the_button_says_whether_it_saves():
    state = _focus(_state(PAST_WEEKDAY), "run")
    assert "sem gravar" in render_text(state)
    state.save = True
    assert "GRAVAR e fechar, sem outra pergunta" in render_text(state)


def test_the_whole_form_is_ascii():
    # Arrows and accents are font-dependent; nothing the form draws may need them.
    state = _state(PAST_WEEKDAY, is_fallback=True)
    for name in ROWS:
        for save in (False, True):
            state.save = save
            assert render_text(_focus(state, name)).isascii(), name


# --------------------------------------------------------------- OSI overlay


def _picker(labels: list[str], cursor: int = 0) -> FormState:
    state = FormState(
        date=DateCursor(day=PAST_WEEKDAY.day, month=PAST_WEEKDAY.month, year=PAST_WEEKDAY.year),
        osi=OsiSpinner(entries=[OsiEntry.from_label(label) for label in labels]),
    )
    _focus(state, "osi")
    state.osi.open_picker()
    state.osi.pick_index = cursor
    return state


def test_the_overlay_replaces_the_form():
    text = render_text(_picker(["OSI 1 | P | A - 1", "coe tech | Fulano - 2"]))
    assert "Escolha a OSI" in text
    assert "Acao" not in text
    assert "coe tech | Fulano - 2" in text


def test_the_overlay_footer_says_choosing_goes_back_to_the_form():
    text = render_text(_picker(["a", "b"]))
    assert "ESCOLHE esta OSI e volta ao formulario" in text
    assert "voltar sem mudar" in text


def test_the_overlay_marks_the_row_under_the_cursor():
    text = render_text(_picker(["a", "b", "c"], cursor=1))
    assert "> \033[7mb\033[0m" in text
    assert "  a" in text


def test_the_overlay_scrolls_to_keep_a_far_cursor_visible():
    labels = [f"OSI {i} | P | A - {i}" for i in range(40)]
    text = render_text(_picker(labels, cursor=39))
    assert "OSI 39 | P | A - 39" in text
    assert "OSI 0 | P | A - 0" not in text
    assert "(40/40)" in text


def test_a_very_long_label_is_cut_instead_of_wrapping():
    text = render_text(_picker(["x" * 200]))
    assert "x" * 200 not in text
    assert "..." in text


def test_no_osi_at_all_says_so_in_red():
    state = FormState(
        date=DateCursor(day=PAST_WEEKDAY.day, month=PAST_WEEKDAY.month, year=PAST_WEEKDAY.year),
        osi=OsiSpinner(entries=[], is_fallback=True),
    )
    text = render_text(state)
    assert RED in text
    assert "Atualizar lista de OSI" in text
