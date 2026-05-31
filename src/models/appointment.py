from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal

from pydantic import BaseModel


class Appointment(BaseModel):
    """
    A single workday appointment: the day it refers to, the four punch times
    (entry, lunch start, lunch end, exit) and an optional free-text OSI.

    Shared across modules (generation, validation, history, browser), so it
    lives in ``models/`` and carries no strategy-specific logic.

    Pydantic model: construct with keyword arguments and dates/times are
    coerced/validated on creation.
    """

    day: date
    entry_time: time
    lunch_start: time
    lunch_end: time
    exit_time: time
    # OSI is optional. Punching WITH an OSI is preferred (it avoids drawing HR /
    # manager attention), but an OSI takes time to be created, which forces
    # punching without one at some month starts -- hence the empty default.
    osi: str = ""

    @property
    def week_day(self) -> int:
        """Day of the week derived from ``day``. 0 = Monday ... 6 = Sunday."""
        return self.day.weekday()

    def get_lunch_interval(self) -> timedelta:
        dt_lunch_start = datetime.combine(self.day, self.lunch_start)
        dt_lunch_end = datetime.combine(self.day, self.lunch_end)
        return dt_lunch_end - dt_lunch_start

    def get_all_intervals(
        self,
    ) -> dict[Literal["morning", "lunch", "afternoon"], timedelta]:
        """
        Duration deltas for:
          - morning   (entry to lunch_start)
          - lunch     (lunch_start to lunch_end)
          - afternoon (lunch_end to exit)
        """
        dt_entry = datetime.combine(self.day, self.entry_time)
        dt_lunch_start = datetime.combine(self.day, self.lunch_start)
        dt_lunch_end = datetime.combine(self.day, self.lunch_end)
        dt_exit = datetime.combine(self.day, self.exit_time)

        return {
            "morning": dt_lunch_start - dt_entry,
            "lunch": dt_lunch_end - dt_lunch_start,
            "afternoon": dt_exit - dt_lunch_end,
        }

    def total_working_hours(self) -> timedelta:
        """Total worked time (morning + afternoon), excluding lunch."""
        intervals = self.get_all_intervals()
        return intervals["morning"] + intervals["afternoon"]

    def __repr__(self) -> str:
        return (
            f"Appointment(day={self.day.isoformat()}, "
            f"entry={self.entry_time.strftime('%H:%M')}, "
            f"lunch_start={self.lunch_start.strftime('%H:%M')}, "
            f"lunch_end={self.lunch_end.strftime('%H:%M')}, "
            f"exit={self.exit_time.strftime('%H:%M')}, "
            f"osi={self.osi!r})"
        )

    __str__ = __repr__
