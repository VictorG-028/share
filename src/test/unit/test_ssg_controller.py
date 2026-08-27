"""
Pure helpers and the verification gate of :class:`SsgController`.

No browser and no network: the gate is what stands between a mistyped field
and a write to a real timekeeping system, so it is tested on canned page state.
"""

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


def _controller(state: dict | None) -> SsgController:
    controller = SsgController()
    controller._page = _FakePage(state)
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
