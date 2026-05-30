from __future__ import annotations

from datetime import date

from models.appointment import Appointment
from modules.strategy.base import AppointmentStrategy
from modules.strategy.static.values import STATIC_TIMES


class StaticStrategy(AppointmentStrategy):
    """
    Deterministic strategy: always the same punch times for a given weekday
    (see :data:`STATIC_TIMES`). This is the default strategy.

    Weekends are not supported -- calling it for Saturday/Sunday raises
    ``NotImplementedError``.
    """

    def generate_for(self, day: date) -> Appointment:
        weekday = day.weekday()
        if weekday not in STATIC_TIMES:
            raise NotImplementedError(
                f"StaticStrategy does not punch on {day.isoformat()} "
                f"(weekday {weekday}: weekend)."
            )
        entry, lunch_start, lunch_end, exit_time = STATIC_TIMES[weekday]
        return Appointment(
            day=day,
            entry_time=entry,
            lunch_start=lunch_start,
            lunch_end=lunch_end,
            exit_time=exit_time,
        )
