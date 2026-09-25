"""
State of the refresh screen: which source to read, and what counts as a day.

Pure, like :mod:`modules.tui.state` -- no ``prompt_toolkit`` here. The screen
exists because ``refresh-osi-list`` is meant to be double-clicked, and a flag
you cannot type is a flag you do not have.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from modules.osi_catalog import SOURCES, SOURCE_TIMESHEET

#: What each source means in one line, shown beside the choice: the names
#: alone do not say that one of them is the slow, complete one.
SOURCE_HINTS = {
    "apontamento": "a lista do '?' do dia mais recente (rapida)",
    "listagem": "todas as suas, com status e validade",
    "ambas": "rotulo real e status na mesma passada",
}

ROWS: tuple[tuple[str, ...], ...] = (
    ("fonte",),
    ("feriado", "fim_de_semana"),
)


@dataclass
class SourceSpinner:
    """The source choice, cycling through :data:`SOURCES`."""

    options: tuple[str, ...] = SOURCES
    index: int = 0

    def current(self) -> str:
        return self.options[self.index % len(self.options)]

    def bump(self, delta: int) -> None:
        self.index = (self.index + delta) % len(self.options)


@dataclass
class RefreshFormState:
    """The whole screen: a spinner and two toggles."""

    source: SourceSpinner = field(default_factory=SourceSpinner)
    include_holidays: bool = False
    include_weekends: bool = False
    row: int = 0
    field: int = 0

    @classmethod
    def initial(cls) -> "RefreshFormState":
        index = SOURCES.index(SOURCE_TIMESHEET) if SOURCE_TIMESHEET in SOURCES else 0
        return cls(source=SourceSpinner(index=index))

    def focus_name(self) -> str:
        return ROWS[self.row][self.field]

    def move_right(self) -> None:
        if self.field + 1 < len(ROWS[self.row]):
            self.field += 1
        else:
            self.row = (self.row + 1) % len(ROWS)
            self.field = 0

    def move_left(self) -> None:
        # Same one-directional navigation as the appointment form: Right
        # always advances (wrapping), Left just steps back within the row.
        self.field = max(0, self.field - 1)

    def bump_value(self, delta: int) -> None:
        name = self.focus_name()
        if name == "fonte":
            self.source.bump(delta)
        elif name == "feriado":
            self.include_holidays = not self.include_holidays
        elif name == "fim_de_semana":
            self.include_weekends = not self.include_weekends

    def try_submit(self) -> list[str]:
        """Nothing here can be invalid, so submitting always yields an argv."""
        return build_refresh_argv(self)


def build_refresh_argv(state: RefreshFormState) -> list[str]:
    """
    Turn the screen into the argv the CLI already understands.

    Only non-defaults are emitted, so the printed command stays the shortest
    one that reproduces the run.
    """
    argv: list[str] = []
    if state.source.current() != SOURCE_TIMESHEET:
        argv += ["--fonte", state.source.current()]
    if state.include_holidays:
        argv.append("--incluir-feriado")
    if state.include_weekends:
        argv.append("--incluir-fim-de-semana")
    return argv
