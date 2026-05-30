from datetime import date, time

import pytest

from models.appointment import Appointment
from modules.validation.validator import validate, validate_list

DAY = date(2026, 5, 29)  # a Friday


def _appt(entry, lunch_start, lunch_end, exit_time, day=DAY):
    return Appointment(
        day=day,
        entry_time=entry,
        lunch_start=lunch_start,
        lunch_end=lunch_end,
        exit_time=exit_time,
    )


def test_valid_sample_week():
    appointments = [
        _appt(time(9, 1), time(12, 5), time(13, 6), time(18, 2)),
        _appt(time(9, 2), time(12, 6), time(13, 7), time(18, 3)),
        _appt(time(9, 3), time(12, 7), time(13, 8), time(18, 4)),
        _appt(time(9, 4), time(12, 8), time(13, 9), time(18, 5)),
        _appt(time(9, 5), time(12, 9), time(13, 10), time(18, 6)),
    ]
    ok, reason = validate_list(appointments)
    assert ok, reason


@pytest.mark.parametrize(
    "entry, lunch_start, lunch_end, exit_time",
    [
        (time(9, 10), time(12, 10), time(13, 1), time(18, 2)),   # entry == lunch_start
        (time(9, 9), time(12, 1), time(13, 9), time(18, 2)),     # lunch_end == entry? exit checks
        (time(9, 16), time(12, 1), time(13, 2), time(18, 16)),   # entry == exit
        (time(9, 1), time(12, 32), time(13, 2), time(18, 32)),   # lunch_end == exit
    ],
)
def test_invalid_due_to_same_minutes(entry, lunch_start, lunch_end, exit_time):
    ok, _ = validate(_appt(entry, lunch_start, lunch_end, exit_time), [])
    assert ok is False


def test_lunch_less_than_one_hour():
    ok, _ = validate(_appt(time(9, 10), time(12, 10), time(12, 59), time(18, 11)), [])
    assert ok is False


def test_span_too_long():
    # 8:01 -> 19:59 is ~12h, outside the 9-10h range
    ok, reason = validate(_appt(time(8, 1), time(12, 2), time(13, 3), time(19, 59)), [])
    assert ok is False
    assert "Rule 10" in reason


def test_minute_zero_rejected():
    ok, reason = validate(_appt(time(9, 0), time(12, 5), time(13, 6), time(18, 2)), [])
    assert ok is False
    assert "Rule 5" in reason


def test_wide_hour_range_is_reachable():
    # entry 10h / exit 19h is now allowed and forms a valid ~9h span
    ok, reason = validate(_appt(time(10, 1), time(13, 5), time(14, 6), time(19, 2)), [])
    assert ok, reason
