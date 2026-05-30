from __future__ import annotations

from typing import Any

from models.appointment import Appointment
from modules.browser.base import BrowserController

_NOT_READY = "PlaywrightController is a stub -- browser layer is a future phase."


class PlaywrightController(BrowserController):
    """
    Drives the site with Playwright (Python, no Node/TS).

    Stub: methods raise until the real site flow is implemented. Requires the
    ``playwright`` package, added as a dependency only when this phase starts.
    """

    def open(self) -> None:
        raise NotImplementedError(_NOT_READY)

    def login(self, credentials: Any | None = None) -> None:
        raise NotImplementedError(_NOT_READY)

    def fill_appointment(self, appointment: Appointment) -> None:
        raise NotImplementedError(_NOT_READY)

    def close(self) -> None:
        raise NotImplementedError(_NOT_READY)
