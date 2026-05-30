from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta

from models.appointment import Appointment


class AppointmentStrategy(ABC):
    """
    GoF Strategy: a way to produce appointment values.

    ``generate_for`` (one day) is the primitive every strategy must implement.
    ``generate_week`` is a convenience helper built on top of it; strategies that
    need cross-day state (e.g. the natural one's per-week uniqueness) override it.
    """

    @abstractmethod
    def generate_for(self, day: date) -> Appointment:
        """Produce the appointment for a single ``day``."""

    def generate_week(self, any_day_in_week: date) -> list[Appointment]:
        """Produce Monday..Friday for the week containing ``any_day_in_week``."""
        monday = any_day_in_week - timedelta(days=any_day_in_week.weekday())
        return [self.generate_for(monday + timedelta(days=offset)) for offset in range(5)]
