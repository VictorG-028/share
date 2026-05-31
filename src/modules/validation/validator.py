from __future__ import annotations

from datetime import datetime, timedelta

from models.appointment import Appointment

################################################################################
# Constraints (the "natural" rules). Shared: used by the random generator loop
# and by sanity tests over the static table. The CSV history is NOT validated on
# load -- it is a trusted record of the real world and may legitimately break
# these synthetic rules.
################################################################################

ENTRY_HOURS = (8, 9, 10)
LUNCH_START_HOURS = (12, 13, 14)
EXIT_HOURS = (17, 18, 19)
MIN_SPAN = timedelta(hours=9)
MAX_SPAN = timedelta(hours=10)
MIN_LUNCH = timedelta(hours=1)

# Rule 4 window size (in punched entries, candidate included).
#
# Real system: rejects a repeated minute within a window centred on the day --
# the current day plus 4 days BACK *and* 4 days FORWARD, counting calendar days
# (weekends/holidays included). It is bidirectional and holiday-aware.
#
# Chosen system (simpler, stricter-friendly): a 7-entry window looking only
# BACKWARD by count (candidate + the 6 previous entries). It is holiday-agnostic
# and counts weekend punches too -- WINDOW_DAYS is in punched days, not calendar
# days -- because weekend work is possible. Backward-only is enough at generation
# time, since no future entries exist yet.
WINDOW_DAYS = 7


def same_minute(a, b) -> bool:
    return a.minute == b.minute


def validate(
    appointment: Appointment, history: list[Appointment]
) -> tuple[bool, str | None]:
    """``(True, None)`` if valid, ``(False, "explanation")`` otherwise."""

    # Rules 1, 2, 3 - minute collisions inside the same appointment
    # NOTE: the real system actually ALLOWS entry == exit minute (1st entry vs
    # 2nd exit); only 1st-exit (lunch_start) and 2nd-entry (lunch_end) are truly
    # constrained there. We deliberately stay stricter (no repeated minute on any
    # field) so nothing ever looks duplicated.
    if same_minute(appointment.entry_time, appointment.exit_time):
        return False, "Rule 1: Entry and exit have same minute"
    if same_minute(appointment.entry_time, appointment.lunch_start):
        return False, "Rule 2: Entry and lunch start have same minute"
    if same_minute(appointment.lunch_end, appointment.exit_time):
        return False, "Rule 3: Lunch end and exit have same minute"

    # Rule 4 - each field's minute must be unique within the sliding window.
    # Single source of truth: validate() always trims to the last WINDOW_DAYS - 1
    # entries here, so callers can pass the full history and never diverge.
    window = history[-(WINDOW_DAYS - 1):] if WINDOW_DAYS > 1 else []
    for past in window:
        if same_minute(appointment.entry_time, past.entry_time):
            return False, "Rule 4: Entry minute already used in history"
        if same_minute(appointment.lunch_start, past.lunch_start):
            return False, "Rule 4: Lunch start minute already used in history"
        if same_minute(appointment.lunch_end, past.lunch_end):
            return False, "Rule 4: Lunch end minute already used in history"
        if same_minute(appointment.exit_time, past.exit_time):
            return False, "Rule 4: Exit minute already used in history"

    # Rule 5 - no time may end on minute 00
    for t in (
        appointment.entry_time,
        appointment.lunch_start,
        appointment.lunch_end,
        appointment.exit_time,
    ):
        if t.minute == 0:
            return False, "Rule 5: Some time has minutes == 00"

    # Rules 6, 7, 9 - allowed hours per field
    if appointment.exit_time.hour not in EXIT_HOURS:
        return False, f"Rule 6: Exit hour must be one of {EXIT_HOURS}"
    if appointment.entry_time.hour not in ENTRY_HOURS:
        return False, f"Rule 7: Entry hour must be one of {ENTRY_HOURS}"
    if appointment.lunch_start.hour not in LUNCH_START_HOURS:
        return False, f"Rule 9: Lunch start hour must be one of {LUNCH_START_HOURS}"

    # Rule 8 - lunch lasts at least one hour
    if appointment.get_lunch_interval() < MIN_LUNCH:
        return False, "Rule 8: Lunch duration is less than 1 hour"

    # Rule 10 - total span from entry to exit between 9h and 10h
    span = datetime.combine(appointment.day, appointment.exit_time) - datetime.combine(
        appointment.day, appointment.entry_time
    )
    if span < MIN_SPAN or span > MAX_SPAN:
        return False, "Rule 10: Total work span not in 9h to 10h range"

    return True, None


def validate_list(appts: list[Appointment]) -> tuple[bool, str | None]:
    """
    Validate a sequence, threading a growing history so Rule 4 (per-field minute
    uniqueness) is enforced across the whole list.
    """
    history: list[Appointment] = []
    for appt in appts:
        ok, reason = validate(appt, history)
        if not ok:
            return False, f"{appt} -> {reason}"
        history.append(appt)
    return True, None
