from __future__ import annotations

from datetime import date

from models.appointment import Appointment
from modules.strategy.base import AppointmentStrategy
from modules.strategy.static.generator import static_times


def _set_number_for_weekday(weekday: int) -> int:
    """
    Map a weekday (``date.weekday()``: 0=Mon .. 6=Sun) to a static set number.

    Mon..Fri -> sets 1..5; Saturday and Sunday both use set 6 (the spare), so
    weekend punches are supported (you may be asked to work a weekend).

    Caveat: there is only one spare set, so punching BOTH weekend days inside the
    same Rule 4 window will collide on minutes (6 sets cannot fill a 7-day window).
    """
    if 0 <= weekday <= 4:
        return weekday + 1
    return 6


class StaticStrategy(AppointmentStrategy):
    """
    Deterministic strategy: the punch times are picked from the six memorizable
    static sets based on the weekday (see :func:`_set_number_for_weekday`). This
    is the default strategy.

    Unlike before, it does NOT raise on weekends -- it uses the spare set 6 -- so
    the orchestrator decides whether a weekend/holiday is actually worked.
    """

    def generate_for(self, day: date) -> Appointment:
        entry, lunch_start, lunch_end, exit_time = static_times(
            _set_number_for_weekday(day.weekday())
        )
        return Appointment(
            day=day,
            entry_time=entry,
            lunch_start=lunch_start,
            lunch_end=lunch_end,
            exit_time=exit_time,
        )
