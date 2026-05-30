from __future__ import annotations

from datetime import date, timedelta

from models.appointment import Appointment
from modules.strategy.base import AppointmentStrategy
from modules.strategy.natural_random.generator import generate_appointment


class NaturalRandomStrategy(AppointmentStrategy):
    """
    Random punch times constrained by the validation rules and the injected
    history. The instance is immutable: generating never mutates the stored
    history.
    """

    def __init__(self, history: list[Appointment] | None = None):
        self._history: list[Appointment] = list(history) if history else []

    def generate_for(self, day: date) -> Appointment:
        return generate_appointment(day, self._history)

    def generate_week(self, any_day_in_week: date) -> list[Appointment]:
        """
        Generate Monday..Friday, feeding each generated day forward so the days
        in the same week stay unique (Rule 4). A local accumulator is used --
        ``self._history`` is never touched.
        """
        monday = any_day_in_week - timedelta(days=any_day_in_week.weekday())
        accumulated = list(self._history)
        week: list[Appointment] = []
        for offset in range(5):
            appointment = generate_appointment(monday + timedelta(days=offset), accumulated)
            week.append(appointment)
            accumulated.append(appointment)
        return week
