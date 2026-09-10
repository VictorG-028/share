import calendar
from datetime import date

import pytest

import main
from modules.tui.state import DateCursor, FormState, OsiSpinner, load_osi_spinner
from modules.osi_catalog.entry import OsiEntry

SATURDAY = date(2026, 5, 30)
FRIDAY = date(2026, 5, 29)  # a week comfortably in the past


@pytest.fixture(autouse=True)
def _no_holidays(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: False)


def _cursor(d: date, *, force: bool = False) -> DateCursor:
    return DateCursor(day=d.day, month=d.month, year=d.year, force=force)


# ------------------------------------------------------------- bump_day


def test_bump_day_rolls_over_the_month_boundary():
    cursor = _cursor(date(2026, 1, 31))
    cursor.bump_day(1)
    assert (cursor.year, cursor.month, cursor.day) == (2026, 2, 1)


def test_bump_day_rolls_over_the_year_boundary():
    cursor = _cursor(date(2026, 12, 31))
    cursor.bump_day(1)
    assert (cursor.year, cursor.month, cursor.day) == (2027, 1, 1)


def test_bump_day_negative_rolls_backward():
    cursor = _cursor(date(2026, 3, 1))
    cursor.bump_day(-1)
    assert (cursor.year, cursor.month, cursor.day) == (2026, 2, 28)


# --------------------------------------------------------- bump_month/year


def test_bump_month_clamps_day_to_the_new_months_length():
    cursor = _cursor(date(2026, 1, 31))
    cursor.bump_month(1)
    assert cursor.month == 2
    assert cursor.day == (29 if calendar.isleap(2026) else 28)
    assert calendar.isleap(2026) is False  # 2026 is not a leap year
    assert cursor.day == 28


def test_bump_month_clamps_in_a_leap_year():
    cursor = _cursor(date(2028, 1, 31))
    cursor.bump_month(1)
    assert calendar.isleap(2028) is True
    assert cursor.day == 29


def test_bump_month_wraps_the_year_forward():
    cursor = _cursor(date(2026, 12, 15))
    cursor.bump_month(1)
    assert (cursor.year, cursor.month) == (2027, 1)


def test_bump_year_clamps_feb_29_on_a_non_leap_year():
    cursor = _cursor(date(2028, 2, 29))
    cursor.bump_year(1)
    assert calendar.isleap(2029) is False
    assert (cursor.year, cursor.month, cursor.day) == (2029, 2, 28)


def test_toggle_force_flips():
    cursor = _cursor(FRIDAY)
    assert cursor.force is False
    cursor.toggle_force()
    assert cursor.force is True
    cursor.toggle_force()
    assert cursor.force is False


# ------------------------------------------------------------------ status


def test_status_today_is_blocked_red_even_with_force():
    cursor = _cursor(date.today(), force=True)
    status = cursor.status()
    assert status.blocked is True
    assert status.color == "red"


def test_status_future_is_blocked_red_even_with_force():
    from datetime import timedelta

    cursor = _cursor(date.today() + timedelta(days=1), force=True)
    status = cursor.status()
    assert status.blocked is True
    assert status.color == "red"


def test_status_is_memoized_per_date_so_repeated_calls_skip_is_holiday(monkeypatch):
    # Regression: render_text() calls status() on every redraw, including a
    # pure Left/Right focus move that never changes the date. Before this was
    # memoized, that repeated skip_reason() -> is_holiday() call could hit the
    # network (BrasilAPI) or re-read a cache file on every keystroke -- a real
    # lag reported when navigating quickly.
    calls = []
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: calls.append(d) or False)
    cursor = _cursor(FRIDAY)

    cursor.status()
    cursor.status()
    cursor.status()
    assert len(calls) == 1  # repeated calls for the same date/force: no extra work

    cursor.bump_day(-1)  # an actual date change (still a weekday) must recompute
    cursor.status()
    assert len(calls) == 2


def test_status_past_weekday_is_clean():
    cursor = _cursor(FRIDAY)
    status = cursor.status()
    assert status.blocked is False
    assert status.color is None


def test_status_past_weekend_is_yellow_and_blocked_without_force():
    cursor = _cursor(SATURDAY, force=False)
    status = cursor.status()
    assert status.blocked is True
    assert status.color == "yellow"


def test_status_past_weekend_is_unblocked_with_force():
    cursor = _cursor(SATURDAY, force=True)
    status = cursor.status()
    assert status.blocked is False


def test_status_past_holiday_is_yellow_and_blocked_without_force(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: True)
    cursor = _cursor(FRIDAY, force=False)
    status = cursor.status()
    assert status.blocked is True
    assert status.color == "yellow"


def test_status_past_holiday_is_unblocked_with_force(monkeypatch):
    monkeypatch.setattr(main, "is_holiday", lambda d, **kw: True)
    cursor = _cursor(FRIDAY, force=True)
    status = cursor.status()
    assert status.blocked is False


# --------------------------------------------------------------- OsiSpinner


def test_osi_spinner_bump_wraps_both_directions():
    entries = [OsiEntry(number="1", label="a"), OsiEntry(number="2", label="b")]
    spinner = OsiSpinner(entries=entries)
    spinner.bump(-1)
    assert spinner.current().number == "2"
    spinner.bump(1)
    assert spinner.current().number == "1"


def test_load_osi_spinner_is_empty_when_nothing_was_ever_captured(monkeypatch):
    # No built-in default OSI: one written into the code is a dead project a
    # month later. Nothing to offer means nothing to punch.
    import modules.osi_catalog as osi_catalog

    monkeypatch.setattr(osi_catalog, "load_catalog", lambda: [])
    monkeypatch.setattr(osi_catalog, "load_last_used", lambda: None)
    spinner = load_osi_spinner()
    assert spinner.is_fallback is True
    assert spinner.entries == []
    assert spinner.current() is None


def test_load_osi_spinner_falls_back_to_the_last_used_alone(monkeypatch):
    import modules.osi_catalog as osi_catalog

    monkeypatch.setattr(osi_catalog, "load_catalog", lambda: [])
    monkeypatch.setattr(osi_catalog, "load_last_used", lambda: "OSI 83270 | P | A - 1")
    spinner = load_osi_spinner()
    assert spinner.is_fallback is True
    assert spinner.current().label == "OSI 83270 | P | A - 1"


def test_load_osi_spinner_matches_last_used_by_label(monkeypatch):
    import modules.osi_catalog as osi_catalog

    entries = [
        OsiEntry.from_label("OSI 1 | P | A - 1"),
        OsiEntry.from_label("coe tech - setembro - 2026 | Fulano - 2"),
    ]
    monkeypatch.setattr(osi_catalog, "load_catalog", lambda: entries)
    monkeypatch.setattr(
        osi_catalog, "load_last_used", lambda: "coe tech - setembro - 2026 | Fulano - 2"
    )
    assert load_osi_spinner().current() == entries[1]


def test_load_osi_spinner_defaults_to_last_used(monkeypatch):
    import modules.osi_catalog as osi_catalog

    entries = [
        OsiEntry(number="1", label="a"),
        OsiEntry(number="2", label="b"),
        OsiEntry(number="3", label="c"),
    ]
    monkeypatch.setattr(osi_catalog, "load_catalog", lambda: entries)
    monkeypatch.setattr(osi_catalog, "load_last_used", lambda: "2")
    spinner = load_osi_spinner()
    assert spinner.is_fallback is False
    assert spinner.current().number == "2"


def test_load_osi_spinner_defaults_to_zero_when_last_used_not_found(monkeypatch):
    import modules.osi_catalog as osi_catalog

    entries = [OsiEntry(number="1", label="a"), OsiEntry(number="2", label="b")]
    monkeypatch.setattr(osi_catalog, "load_catalog", lambda: entries)
    monkeypatch.setattr(osi_catalog, "load_last_used", lambda: "does-not-exist")
    spinner = load_osi_spinner()
    assert spinner.current().number == "1"


# ------------------------------------------------------------- OSI overlay


def _picker_state(labels: list[str]) -> FormState:
    state = FormState(
        date=DateCursor(day=29, month=5, year=2026),
        osi=OsiSpinner(entries=[OsiEntry.from_label(label) for label in labels]),
    )
    state.row = 1  # the OSI row
    return state


def test_opening_the_picker_starts_on_what_is_selected():
    state = _picker_state(["a", "b", "c"])
    state.osi.bump(1)
    state.osi.open_picker()
    assert state.osi.picking is True
    assert state.osi.pick_index == 1


def test_down_moves_down_the_list_and_leaves_the_form_alone():
    # bump_value(-1) is what the Down arrow sends; in a list that is the row
    # below, not "one less".
    state = _picker_state(["a", "b", "c"])
    state.osi.open_picker()
    state.bump_value(-1)
    assert state.osi.pick_index == 1
    assert state.osi.index == 0  # nothing chosen yet


def test_choosing_takes_the_highlighted_row_and_closes():
    state = _picker_state(["a", "b", "c"])
    state.osi.open_picker()
    state.bump_value(-1)
    state.osi.choose()
    assert state.osi.picking is False
    assert state.osi.current().label == "b"


def test_cancelling_the_picker_keeps_the_old_selection():
    state = _picker_state(["a", "b", "c"])
    state.osi.open_picker()
    state.bump_value(-1)
    state.osi.cancel_pick()
    assert state.osi.picking is False
    assert state.osi.current().label == "a"


def test_the_picker_wraps_at_both_ends():
    state = _picker_state(["a", "b"])
    state.osi.open_picker()
    state.osi.move_pick(-1)
    assert state.osi.pick_index == 1


def test_submitting_is_blocked_without_any_osi():
    state = _picker_state([])
    state.date = DateCursor(day=29, month=5, year=2026)
    assert state.block_reason() is not None
    assert state.try_submit() is None
