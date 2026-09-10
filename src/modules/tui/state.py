"""
Pure state for the grid form -- no ``prompt_toolkit`` import here on purpose,
so this is plain-pytest testable without a terminal.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
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


def _compute_status(day: int, month: int, year: int, force: bool) -> DateStatus:
    # Lazy import: avoids modules/ depending on main.py at import time, same
    # discipline main.py's own punch()/refresh_osi_list() already use for the
    # browser stack. Reused, not reimplemented: the past/weekend/holiday
    # rules live in exactly one place.
    from main import skip_reason

    target = date(year, month, day)
    reason = skip_reason(target, force=force)
    if target >= date.today():
        # The unconditional rule: force never lifts this one.
        return DateStatus(blocked=True, color="red", message=reason or "")
    if reason is None:
        return DateStatus(blocked=False, color=None, message="")
    return DateStatus(blocked=True, color="yellow", message=reason)


@dataclass
class DateCursor:
    day: int
    month: int
    year: int
    force: bool = False
    # Memoized status, keyed by the (day, month, year, force) it was computed
    # for -- per-instance, not global, so it can never leak between tests or
    # sessions. `field(...)` because a dict/tuple default must not be shared
    # across instances.
    _status_cache: dict = field(default_factory=dict, init=False, repr=False, compare=False)

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
        # render_text() calls this on every redraw -- including a pure
        # Left/Right focus move, which never changes the date -- and
        # skip_reason() can hit is_holiday(), which can hit the network
        # (BrasilAPI) or at least re-read a JSON cache file from disk.
        # Memoized per instance by (day, month, year, force) so navigating
        # focus around never re-triggers that work; only an actual date/force
        # change does. Unbounded but harmless: one form has a handful of
        # distinct dates visited per session, never thousands.
        key = (self.day, self.month, self.year, self.force)
        if key not in self._status_cache:
            self._status_cache[key] = _compute_status(*key)
        return self._status_cache[key]


@dataclass
class OsiSpinner:
    """
    The OSI choice: ``entries`` may be empty, and then nothing can be punched.

    ``picking`` is the overlay -- the same list, shown whole, with its own
    cursor. It exists because cycling one line at a time with the arrows is
    fine for two OSIs and useless for twenty, half of them opened by the
    manager with someone else's name on them.
    """

    entries: list[OsiEntry]
    index: int = 0
    is_fallback: bool = False
    picking: bool = False
    pick_index: int = 0

    def current(self) -> OsiEntry | None:
        if not self.entries:
            return None
        return self.entries[self.index % len(self.entries)]

    def bump(self, delta: int) -> None:
        if self.entries:
            self.index = (self.index + delta) % len(self.entries)

    # ------------------------------------------------------------- overlay

    def open_picker(self) -> None:
        """Open the list positioned on what is selected now."""
        if self.entries:
            self.picking = True
            self.pick_index = self.index % len(self.entries)

    def move_pick(self, delta: int) -> None:
        if self.entries:
            self.pick_index = (self.pick_index + delta) % len(self.entries)

    def choose(self) -> None:
        """Take the highlighted row and close."""
        self.index = self.pick_index
        self.picking = False

    def cancel_pick(self) -> None:
        """Close without changing the selection."""
        self.picking = False


def load_osi_spinner() -> OsiSpinner:
    """
    The catalog, or the last-used OSI alone, or nothing at all.

    There is no built-in default OSI any more: one written into the code is a
    dead project a month later (82695 was), and booking the wrong OSI is worse
    than being told to run ``refresh-osi-list``.
    """
    from modules.osi_catalog import load_catalog, load_last_used

    entries = load_catalog()
    last_used = load_last_used()
    if not entries:
        if not last_used:
            return OsiSpinner(entries=[], is_fallback=True)
        return OsiSpinner(
            entries=[OsiEntry.from_label(last_used)], is_fallback=True
        )

    index = next(
        (i for i, entry in enumerate(entries) if entry.label == last_used), None
    )
    if index is None:
        # Files written before the catalog went free-text hold a bare number.
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
        if self.osi.picking:
            # The overlay owns the arrows while it is up -- and inverts them:
            # on the form Down means "one less" (a day, a month), in a list it
            # means the row below.
            self.osi.move_pick(-delta)
            return
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

    def block_reason(self) -> str | None:
        """Why Enter would not submit, or ``None``. Also what the form shows."""
        status = self.date.status()
        if status.blocked:
            return status.message
        if self.osi.current() is None:
            return "sem OSI para apontar -- rode refresh-osi-list"
        return None

    def try_submit(self) -> list[str] | None:
        """``None`` if blocked -- checked regardless of current focus."""
        if self.block_reason() is not None:
            return None
        from modules.tui.argv_builder import build_argv

        return build_argv(self)
