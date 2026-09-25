"""
Which day's OSI list to read, decided from what the site itself says.

The site's OSI list is filtered by day on the server, and it really does
differ: on 2026-09-10 the same account got 17 entries for 10/09, 16 for 03/09,
15 for 27/08 and 4 for 01/07. So "which day" is not a detail -- reading an old
day hands you an old menu.

Eligibility is read from the day panel's own heading, never computed:

    Sem registro 09/09/2026 QUARTA-FEIRA Sobre Aviso
    Sem registro 07/09/2026 FERIADO      Sobre Aviso

The site writes ``FERIADO`` in place of the weekday. That is the only source
that knows a company or regional holiday -- a national-holiday calendar does
not -- which is why this reads the screen instead of asking
``modules.holiday.service``.

Everything here is pure: it takes the raw panels
(:meth:`SsgController.days_on_screen`) and returns dates. No browser, no clock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

#: The heading word that means "not a working day of the usual kind".
HOLIDAY_WORD = "FERIADO"
#: The two weekend words, as the site spells them (accented, upper case).
WEEKEND_WORDS = {"SÁBADO", "SABADO", "DOMINGO"}

#: The heading is ``<selo> <data> <PALAVRA> <resto>``; the word we want is the
#: token right after the date. Kept as a regex over the collapsed heading so a
#: change in the badges around it does not move the answer.
_WORD_AFTER_DATE = re.compile(r"\d{2}/\d{2}/\d{4}\s+([^\s]+)")


@dataclass(frozen=True)
class DayPanel:
    """One day as the screen shows it."""

    day: date
    word: str
    has_appointment: bool

    @property
    def is_holiday(self) -> bool:
        return self.word.upper() == HOLIDAY_WORD

    @property
    def is_weekend(self) -> bool:
        return self.word.upper() in WEEKEND_WORDS


def parse_panels(raw: list[dict]) -> list[DayPanel]:
    """
    Turn :meth:`SsgController.days_on_screen` output into panels, oldest first.

    A panel whose date or word cannot be read is dropped rather than guessed:
    the cost of skipping one candidate day is walking to the next one, while
    the cost of misreading a holiday as a workday is a list from a day the
    site refuses to populate.
    """
    panels: list[DayPanel] = []
    for item in raw:
        try:
            day = datetime.strptime(str(item.get("stamp")), "%d/%m/%Y").date()
        except (ValueError, TypeError):
            continue
        match = _WORD_AFTER_DATE.search(str(item.get("heading") or ""))
        if not match:
            continue
        panels.append(
            DayPanel(
                day=day,
                word=match.group(1),
                has_appointment=bool(item.get("appointments")),
            )
        )
    return sorted(panels, key=lambda panel: panel.day)


def eligible_days(
    panels: list[DayPanel],
    *,
    include_holidays: bool = False,
    include_weekends: bool = False,
) -> list[date]:
    """
    The candidate days, **most recent first** -- the ladder to walk down.

    Today is included when the screen shows it: reading a day's list is a GET,
    it creates nothing, and the newest day gives the freshest menu. (Punching
    today is a different matter and stays forbidden in ``main.skip_reason``.)

    The two flags exist because working a holiday or a weekend is a real thing
    that happens; when you did work then, that day's list is the one you want.
    """
    keep: list[date] = []
    for panel in panels:
        if panel.is_holiday and not include_holidays:
            continue
        if panel.is_weekend and not include_weekends:
            continue
        keep.append(panel.day)
    return sorted(keep, reverse=True)
