"""
Pure helpers and the verification gate of :class:`SsgController`.

No browser and no network: the gate is what stands between a mistyped field
and a write to a real timekeeping system, so it is tested on canned page state.
"""

import re
from datetime import date, time

import pytest

from models.appointment import Appointment
from modules.browser.ssg_controller import (
    FieldMismatch,
    SsgController,
    SsgError,
    date_digits,
    day_locator,
    to_digits,
    to_display,
    worked_hours,
)

DAY = date(2026, 8, 26)  # the day proven end-to-end against the real site
APPOINTMENT = Appointment(
    day=DAY,
    entry_time=time(9, 3),
    lunch_start=time(12, 7),
    lunch_end=time(13, 8),
    exit_time=time(18, 4),
)

VALID_STATE = {
    "access": [["09:03", "12:07"], ["13:08", "18:04"]],
    "hours": "08:00",
    "osi": "OSI 82695 | Faturamento Assistencial SECONCI | Carga base historica - 417293",
    "note": "",
    "absence": 0,
}


# ------------------------------------------------------------------- helpers


def test_to_digits_drops_the_separator():
    # Masked fields take digits only; typing "09:03" reshuffles the mask.
    assert to_digits(time(9, 3)) == "0903"
    assert to_digits(time(18, 4)) == "1804"


def test_to_display_is_what_the_mask_renders():
    assert to_display(time(9, 3)) == "09:03"


def test_worked_hours_excludes_lunch():
    # 09:03->12:07 (3h04) + 13:08->18:04 (4h56) = 08:00, the site's "Horas".
    assert worked_hours(APPOINTMENT) == time(8, 0)


def test_date_digits_is_brazilian_order():
    assert date_digits(DAY) == "26082026"


def test_day_locator_looks_for_the_brazilian_date():
    assert "26/08/2026" in day_locator(DAY)


# ---------------------------------------------------------------------- gate


class _FakePage:
    """Returns canned state for read_day, ignoring the JS it is handed."""

    def __init__(self, state: dict | None) -> None:
        self.state = state

    def evaluate_json(self, expression: str):  # noqa: ARG002 - shape only
        return self.state


def _controller(state: dict | None, *, selected: str | None = VALID_STATE["osi"]) -> SsgController:
    controller = SsgController(osi=selected)
    controller._page = _FakePage(state)
    # What _fill_osi would have stored: the value the site put in the field.
    controller.osi_selected = selected
    return controller


def test_verify_accepts_a_matching_day():
    assert _controller(VALID_STATE).verify(APPOINTMENT) == VALID_STATE


def test_verify_rejects_a_wrong_time():
    broken = {**VALID_STATE, "access": [["09:30", "12:07"], ["13:08", "18:04"]]}
    with pytest.raises(FieldMismatch):
        _controller(broken).verify(APPOINTMENT)


def test_verify_rejects_wrong_hours():
    with pytest.raises(FieldMismatch):
        _controller({**VALID_STATE, "hours": "07:00"}).verify(APPOINTMENT)


def test_verify_rejects_another_osi():
    with pytest.raises(FieldMismatch):
        _controller({**VALID_STATE, "osi": "OSI 11111 | outra coisa"}).verify(APPOINTMENT)


def test_verify_rejects_a_neighbouring_row_of_the_same_project():
    # The whole point of comparing the exact string: two rows of one project
    # differ only at the tail, and a click that slipped one row lands here.
    sibling = VALID_STATE["osi"].replace("- 417293", "- 417294")
    with pytest.raises(FieldMismatch):
        _controller({**VALID_STATE, "osi": sibling}).verify(APPOINTMENT)


def test_verify_tolerates_respacing_from_the_server():
    # Same value, re-rendered by the server after a save; only runs of
    # whitespace differ, which must not read as a divergence.
    respaced = VALID_STATE["osi"].replace(" | ", "  |  ")
    assert _controller({**VALID_STATE, "osi": respaced}).verify(APPOINTMENT)


def test_verify_refuses_a_day_where_no_osi_was_picked():
    with pytest.raises(FieldMismatch):
        _controller(VALID_STATE, selected=None).verify(APPOINTMENT)


def test_verify_accepts_the_semicolon_the_site_writes_itself():
    # We always leave the note empty; the site stores ";" for an empty note,
    # so a day read back from the server shows ";" and is still untouched.
    assert _controller({**VALID_STATE, "note": ";"}).verify(APPOINTMENT)


def test_verify_rejects_a_note_someone_typed():
    with pytest.raises(FieldMismatch):
        _controller({**VALID_STATE, "note": "home office"}).verify(APPOINTMENT)


def test_verify_rejects_absence_allowance():
    with pytest.raises(FieldMismatch):
        _controller({**VALID_STATE, "absence": 1}).verify(APPOINTMENT)


def test_verify_rejects_a_day_that_is_not_on_screen():
    with pytest.raises(SsgError):
        _controller(None).verify(APPOINTMENT)


def test_using_the_controller_before_open_is_an_error():
    with pytest.raises(SsgError):
        SsgController().page


def test_days_with_appointments_parses_brazilian_dates_oldest_first():
    controller = _controller(["03/09/2026", "26/08/2026"])
    assert controller.days_with_appointments() == [date(2026, 8, 26), date(2026, 9, 3)]


# ------------------------------------------------------------------ osi list


class _OsiHelpPage:
    """
    Enough page for list_osi_help_items: the day is never collapsed, the "?"
    click can swap the day's state (to exercise the tripwire), the modal's
    rows are canned, and "Fechar" always works.
    """

    def __init__(self, before: dict, after: dict, rows: list[str]) -> None:
        self.day = before
        self.after = after
        self.rows = rows
        self.clicked: list[str] = []

    def evaluate(self, expression: str):  # noqa: ARG002 - shape only
        return False  # not collapsed; modal gone after "Fechar"

    def evaluate_json(self, expression: str):
        if "col-item" in expression:
            return self.rows
        if "input-clock-in" in expression:
            return self.day
        return {"access": 2, "appointment": 1}

    def click(self, locator: str) -> None:
        self.clicked.append(locator)
        if "button-show-items" in locator:
            self.day = self.after

    def wait_for(self, locator: str, *, timeout_seconds: float = 20) -> None:  # noqa: ARG002
        pass


@pytest.fixture
def no_sleep(monkeypatch):
    from modules.browser import ssg_controller

    monkeypatch.setattr(ssg_controller._time, "sleep", lambda _seconds: None)


def test_list_osi_help_items_returns_the_rows_and_closes_the_modal(no_sleep):
    rows = ["OSI 83270 | P | A - 1", "OSI 83174 | P | A - 1"]
    page = _OsiHelpPage(VALID_STATE, VALID_STATE, rows)
    controller = SsgController()
    controller._page = page
    assert controller.list_osi_help_items(DAY) == rows
    assert any("Fechar" in locator for locator in page.clicked)


def test_list_osi_help_items_refuses_when_the_day_changed_underneath(no_sleep):
    changed = {**VALID_STATE, "hours": "07:00"}
    controller = SsgController()
    controller._page = _OsiHelpPage(VALID_STATE, changed, ["OSI 1 | P | A - 1"])
    with pytest.raises(SsgError):
        controller.list_osi_help_items(DAY)


# ------------------------------------------------------------------ osi pick


class _OsiPickPage:
    """
    Enough page to pick an OSI from the "?" list: the day is expanded and has
    its rows, the modal lists ``rows``, and clicking a row's select button
    makes the site write that row's own text into the field -- which is what
    the real widget does.
    """

    def __init__(self, rows: list[str], *, fills: bool = True) -> None:
        self.rows = rows
        self.fills = fills
        self.state = {**VALID_STATE, "osi": ""}
        self.clicked: list[str] = []

    def evaluate(self, expression: str):  # noqa: ARG002 - shape only
        return False  # never collapsed; no modal left open

    def evaluate_json(self, expression: str):
        if "col-item" in expression:
            return self.rows
        if "input-clock-in" in expression:
            return self.state
        return {"access": 2, "appointment": 1}

    def click(self, locator: str) -> None:
        self.clicked.append(locator)
        match = re.search(r"tr\.dynamic'\)\]\[(\d+)\]", locator)
        if match and "button-select" in locator and self.fills:
            self.state = {**self.state, "osi": self.rows[int(match.group(1))]}

    def wait_for(self, locator: str, *, timeout_seconds: float = 20) -> None:  # noqa: ARG002
        pass


#: Shaped like the real list: one OSI of your own (numbered) and two the
#: manager opened for the team, which carry no number at all -- and differ
#: only by month, which is where an ambiguous selector comes from.
PICK_ROWS = [
    "OSI 83270 | Faturamento Assistencial SECONCI | Carga base historica - 417293",
    "coe tech - setembro - 2026 | Walber Hugo da Silva - 427465",
    "coe tech - agosto - 2026 | Walber Hugo da Silva - 411111",
]


def _pick_controller(selector: str | None, rows=PICK_ROWS, *, fills: bool = True):
    controller = SsgController(osi=selector)
    controller._page = _OsiPickPage(rows, fills=fills)
    return controller


def test_fill_osi_picks_an_unnumbered_row_by_its_label(no_sleep):
    controller = _pick_controller("coe tech - setembro - 2026 | Walber Hugo da Silva - 427465")
    controller._fill_osi(DAY)
    assert controller.osi_selected == PICK_ROWS[1]


def test_fill_osi_still_accepts_a_bare_number(no_sleep):
    controller = _pick_controller("83270")
    controller._fill_osi(DAY)
    assert controller.osi_selected == PICK_ROWS[0]


def test_fill_osi_refuses_an_ambiguous_selector_and_closes_the_modal(no_sleep):
    controller = _pick_controller("coe tech")  # setembro and agosto both match
    with pytest.raises(SsgError):
        controller._fill_osi(DAY)
    assert any("Fechar" in locator for locator in controller.page.clicked)
    assert not any("button-select" in locator for locator in controller.page.clicked)


def test_fill_osi_refuses_a_selector_the_day_does_not_offer(no_sleep):
    controller = _pick_controller("OSI 82695")
    with pytest.raises(SsgError):
        controller._fill_osi(DAY)


def test_fill_osi_refuses_when_no_osi_was_chosen(no_sleep):
    controller = _pick_controller(None)
    with pytest.raises(SsgError):
        controller._fill_osi(DAY)
    assert not controller.page.clicked  # the "?" is never even opened


def test_fill_osi_refuses_when_the_field_stays_empty(no_sleep):
    controller = _pick_controller("83270", fills=False)
    with pytest.raises(FieldMismatch):
        controller._fill_osi(DAY)
