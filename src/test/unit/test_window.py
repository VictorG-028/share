"""Rule 4 sliding-window behaviour (WINDOW_DAYS)."""

from datetime import date, time

from models.appointment import Appointment
from modules.validation.validator import WINDOW_DAYS, validate

DAY = date(2026, 5, 29)


def _candidate(entry_min: int) -> Appointment:
    # Valid shape; only the entry minute varies. The non-entry minutes (50/55/40)
    # are chosen disjoint from the history's (05/06/02), so ONLY the entry field
    # can ever collide -- isolating the window behaviour. Span 9:MM->18:40 stays
    # within 9-10h for small MM.
    return Appointment(
        day=DAY,
        entry_time=time(9, entry_min),
        lunch_start=time(12, 50),
        lunch_end=time(13, 55),
        exit_time=time(18, 40),
    )


def _hist(entry_min: int) -> Appointment:
    return Appointment(
        day=DAY,
        entry_time=time(9, entry_min),
        lunch_start=time(12, 5),
        lunch_end=time(13, 6),
        exit_time=time(18, 2),
    )


def test_window_is_seven():
    assert WINDOW_DAYS == 7


def test_repeat_within_window_is_rejected():
    # 6 prior entries (window minus candidate); candidate repeats the entry
    # minute of one of them -> rejected by Rule 4.
    history = [_hist(m) for m in (10, 11, 12, 13, 14, 15)]
    ok, reason = validate(_candidate(15), history)
    assert ok is False
    assert "Rule 4" in reason


def test_repeat_just_outside_window_is_allowed():
    # The colliding entry sits 7 entries back (one slot beyond the 6-entry
    # window), so validate() trims it out and the candidate is accepted.
    history = [_hist(15)] + [_hist(m) for m in (20, 21, 22, 23, 24, 25)]
    ok, reason = validate(_candidate(15), history)
    assert ok, reason
