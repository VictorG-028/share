"""
State of the start menu: which operation to open.

Pure, like the other ``*_state`` modules. The menu only *chooses*; the
operation it names runs after the screen closes, in ``main.cli``. "Criar OSI"
is listed but closed: choosing it still returns its key, and the caller prints
the notice -- so the message lands in the console, where the usual
"press Enter to close" pause already waits for the Enter that closes it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    hint: str
    closed: bool = False


APONTAR = "apontar"
ATUALIZAR = "atualizar"
CRIAR = "criar"

ITEMS: tuple[MenuItem, ...] = (
    MenuItem(APONTAR, "Apontar", "digita (ou grava) o ponto de um dia"),
    MenuItem(ATUALIZAR, "Atualizar lista de OSI", "le a lista do site; nada e gravado"),
    MenuItem(CRIAR, "Criar OSI", "INTERDITADO", closed=True),
)


@dataclass
class MenuState:
    focus: int = 0

    def current(self) -> MenuItem:
        return ITEMS[self.focus]

    def move_next(self) -> None:
        self.focus = (self.focus + 1) % len(ITEMS)

    def move_prev(self) -> None:
        self.focus = (self.focus - 1) % len(ITEMS)

    def activate(self) -> str:
        """The key of the item to open (closed ones included)."""
        return self.current().key
