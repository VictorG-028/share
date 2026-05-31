from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from models.appointment import Appointment
from modules.validation.validator import (
    ENTRY_HOURS,
    EXIT_HOURS,
    LUNCH_START_HOURS,
    validate,
)

MAX_ATTEMPTS = 1000


def generate_appointment(day: date, history: list[Appointment]) -> Appointment:
    """
    Draw random punch times for ``day`` until they satisfy every rule in
    :func:`validate`, considering up to the last 5 history entries.

    Pure function: it never mutates ``history``. The full history can be passed;
    :func:`validate` trims it to the Rule 4 window internally.
    """
    for _ in range(MAX_ATTEMPTS):
        entry_time = time(random.choice(ENTRY_HOURS), random.randint(1, 59))
        lunch_start = time(random.choice(LUNCH_START_HOURS), random.randint(1, 59))

        lunch_duration = timedelta(hours=1, minutes=random.randint(0, 15))
        lunch_end = (datetime.combine(day, lunch_start) + lunch_duration).time()

        exit_time = time(random.choice(EXIT_HOURS), random.randint(1, 59))

        appointment = Appointment(
            day=day,
            entry_time=entry_time,
            lunch_start=lunch_start,
            lunch_end=lunch_end,
            exit_time=exit_time,
        )

        ok, _reason = validate(appointment, history)
        if ok:
            return appointment

    raise RuntimeError(
        f"Could not generate a valid appointment for {day.isoformat()} "
        f"after {MAX_ATTEMPTS} attempts."
    )
