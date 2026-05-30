from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from models.appointment import Appointment


class BrowserController(ABC):
    """
    Contract for driving the appointment website. Two implementations will exist
    -- Playwright (Python) and the home-grown mouse/keyboard framework -- so the
    same orchestration code can compare which one drives the browser better.

    The contract is lifecycle + fill-per-day; each implementation hides the
    actual form/UI details so the orchestrator stays browser-agnostic.
    """

    @abstractmethod
    def open(self) -> None:
        """Start the browser/session."""

    def login(self, credentials: Any | None = None) -> None:
        """Authenticate if needed. Default: no-op."""

    @abstractmethod
    def fill_appointment(self, appointment: Appointment) -> None:
        """Enter and submit a single day's appointment on the site."""

    @abstractmethod
    def close(self) -> None:
        """Tear down the browser/session."""

    def __enter__(self) -> "BrowserController":
        self.open()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
