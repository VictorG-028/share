"""
Pure state for the grid form -- no ``prompt_toolkit`` import here on purpose,
so this is plain-pytest testable without a terminal.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from modules.osi_catalog.entry import OsiEntry

_WEEKDAY_NAMES_PT = [
    "Segunda-feira",
    "Terca-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sabado",
    "Domingo",
]


@dataclass
class DateStatus:
    blocked: bool
    color: str | None  # "red" | "yellow" | None
    message: str


@dataclass
class DateCursor:
    day: int
    month: int
    year: int
    force: bool = False

    def as_date(self) -> date:
        return date(self.year, self.month, self.day)

    def weekday_name(self) -> str:
        return _WEEKDAY_NAMES_PT[self.as_date().weekday()]

    def bump_day(self, delta: int) -> None:
        """Real calendar rollover: day 31 + 1 -> day 1 of next month."""
        moved = self.as_date() + timedelta(days=delta)
        self.day, self.month, self.year = moved.day, moved.month, moved.year

    def _clamp_day(self) -> None:
        last_day = calendar.monthrange(self.year, self.month)[1]
        self.day = min(self.day, last_day)

    def bump_month(self, delta: int) -> None:
        """Shift the month, then clamp the day (31/01 -> Fev vira 28 ou 29)."""
        index = (self.month - 1) + delta
        self.year += index // 12
        self.month = index % 12 + 1
        self._clamp_day()

    def bump_year(self, delta: int) -> None:
        self.year += delta
        self._clamp_day()

    def toggle_force(self) -> None:
        self.force = not self.force

    def status(self) -> DateStatus:
        # Lazy import: avoids modules/ depending on main.py at import time,
        # same discipline main.py's own punch()/refresh_osi_list() already
        # use for the browser stack. Reused, not reimplemented: the
        # past/weekend/holiday rules live in exactly one place.
        from main import skip_reason

        target = self.as_date()
        reason = skip_reason(target, force=self.force)
        if target >= date.today():
            # The unconditional rule: force never lifts this one.
            return DateStatus(blocked=True, color="red", message=reason or "")
        if reason is None:
            return DateStatus(blocked=False, color=None, message="")
        return DateStatus(blocked=True, color="yellow", message=reason)


@dataclass
class OsiSpinner:
    entries: list[OsiEntry]
    index: int = 0
    is_fallback: bool = False

    def current(self) -> OsiEntry:
        return self.entries[self.index % len(self.entries)]

    def bump(self, delta: int) -> None:
        self.index = (self.index + delta) % len(self.entries)


def load_osi_spinner() -> OsiSpinner:
    from modules.browser.ssg_controller import DEFAULT_OSI_NUMBER
    from modules.osi_catalog import load_catalog, load_last_used

    entries = load_catalog()
    if not entries:
        fallback = OsiEntry(
            number=DEFAULT_OSI_NUMBER,
            label=f"OSI {DEFAULT_OSI_NUMBER} (padrao)",
        )
        return OsiSpinner(entries=[fallback], is_fallback=True)

    last_used = load_last_used()
    index = next(
        (i for i, entry in enumerate(entries) if entry.number == last_used), 0
    )
    return OsiSpinner(entries=entries, index=index)


ROWS: tuple[tuple[str, ...], ...] = (
    ("day", "month", "year", "force"),
    ("osi",),
    ("save",),
)


@dataclass
class FormState:
    date: DateCursor
    osi: OsiSpinner
    save: bool = True
    row: int = 0
    field: int = 0

    @classmethod
    def initial(cls) -> "FormState":
        today = date.today()
        return cls(
            date=DateCursor(day=today.day, month=today.month, year=today.year),
            osi=load_osi_spinner(),
        )

    def focus_name(self) -> str:
        return ROWS[self.row][self.field]

    def move_right(self) -> None:
        if self.field + 1 < len(ROWS[self.row]):
            self.field += 1
        else:
            self.row = (self.row + 1) % len(ROWS)
            self.field = 0

    def move_left(self) -> None:
        # Never changes row -- navigation is one-directional (confirmed
        # explicitly: Right always advances, including wrap-around; Left
        # just stops at the first field of the current row).
        self.field = max(0, self.field - 1)

    def bump_value(self, delta: int) -> None:
        name = self.focus_name()
        if name == "day":
            self.date.bump_day(delta)
        elif name == "month":
            self.date.bump_month(delta)
        elif name == "year":
            self.date.bump_year(delta)
        elif name == "force":
            self.date.toggle_force()
        elif name == "osi":
            self.osi.bump(delta)
        elif name == "save":
            self.save = not self.save

    def try_submit(self) -> list[str] | None:
        """``None`` if blocked -- checked regardless of current focus."""
        if self.date.status().blocked:
            return None
        from modules.tui.argv_builder import build_argv

        return build_argv(self)
