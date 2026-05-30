from __future__ import annotations

from typing import Any

from models.appointment import Appointment
from modules.browser.base import BrowserController

_NOT_READY = "InputController is a stub -- browser layer is a future phase."


class InputController(BrowserController):
    """
    Drives the site with the home-grown mouse/keyboard framework (Python).

    Same contract as :class:`PlaywrightController` -- the duplicated behaviour is
    intentional, so the two can be compared on equal footing using the very same
    generated appointment values.

    Stub: methods raise until the real flow is implemented.
    """

    def open(self) -> None:
        raise NotImplementedError(_NOT_READY)

    def login(self, credentials: Any | None = None) -> None:
        raise NotImplementedError(_NOT_READY)

    def fill_appointment(self, appointment: Appointment) -> None:
        raise NotImplementedError(_NOT_READY)

    def close(self) -> None:
        raise NotImplementedError(_NOT_READY)
