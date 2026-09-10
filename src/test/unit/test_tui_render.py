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


# --------------------------------------------------------------- OSI overlay


def _picker(labels: list[str], cursor: int = 0) -> FormState:
    state = FormState(
        date=DateCursor(day=PAST_WEEKDAY.day, month=PAST_WEEKDAY.month, year=PAST_WEEKDAY.year),
        osi=OsiSpinner(entries=[OsiEntry.from_label(label) for label in labels]),
    )
    state.row = 1
    state.osi.open_picker()
    state.osi.pick_index = cursor
    return state


def test_the_overlay_replaces_the_form():
    text = render_text(_picker(["OSI 1 | P | A - 1", "coe tech | Fulano - 2"]))
    assert "Escolha a OSI" in text
    assert "Salvar?" not in text
    assert "coe tech | Fulano - 2" in text


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
    assert "rode --refresh-osi-list" in text
