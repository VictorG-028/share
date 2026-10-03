"""
The footer every screen shows: which keys do what *right now*.

Pure and ASCII-only on purpose. Arrows are spelled out (``[CIMA]``) instead of
drawn (``↑``): whether a glyph shows up depends on the console *font*, not only
on its encoding, and the legacy cmd fonts print ``?`` for it. Plain ASCII is
the one thing every console this runs in (PowerShell, cmd, Git Bash, the
double-clicked .exe) draws the same way.

Each line is ``[TECLA] / [TECLA]`` in a fixed-width column, then the effect,
whose first word says what kind of effect it is: ``MUDA`` (changes a value),
``ABRE`` (opens a list) or ``EXECUTA`` (does the thing and closes). That is
the answer to "what happens if I press this?", which the old footer never gave.
"""

from __future__ import annotations

NAV = "[CIMA] / [BAIXO]"
ADVANCE = "[ENTER] / [ESPACO]"
ADVANCE_RIGHT = "[ENTER] / [ESPACO] / [DIR]"
LEFT_RIGHT = "[ESQ] / [DIR]"
LEFT = "[ESQ]"
CANCEL = "[ESC] / [BACKSPACE] / [CTRL-C]"
BACK = "[ESC] / [BACKSPACE]"
CTRL_C = "[CTRL-C]"

#: Every key combination that can appear, so the effect column starts at the
#: same place on every screen and in every focus -- the footer never jumps.
KEYS_WIDTH = max(
    len(keys)
    for keys in (NAV, ADVANCE, ADVANCE_RIGHT, LEFT_RIGHT, LEFT, CANCEL, BACK, CTRL_C)
)

# Modes: what the focus is standing on.
VALUE = "value"  # a day/month/year/toggle/spinner: Enter changes it
OSI = "osi"  # the OSI row: Enter opens the list
RUN = "run"  # the final button: Enter executes
PICKER = "picker"  # inside the OSI list
MENU = "menu"  # the start menu


def _line(keys: str, effect: str) -> str:
    return f"  {keys:<{KEYS_WIDTH}}   {effect}"


def legend(mode: str, *, run_effect: str = "") -> str:
    """The footer for ``mode``; ``run_effect`` finishes the ``EXECUTA`` line."""
    if mode == VALUE:
        rows = [
            (ADVANCE_RIGHT, "MUDA o valor para frente"),
            (LEFT, "MUDA o valor para tras"),
            (NAV, "mudam de linha"),
            (CANCEL, "cancelar e fechar (nada e feito)"),
        ]
    elif mode == OSI:
        rows = [
            (ADVANCE, "ABRE a lista de OSIs"),
            (LEFT_RIGHT, "MUDA a OSI sem abrir a lista"),
            (NAV, "mudam de linha"),
            (CANCEL, "cancelar e fechar (nada e feito)"),
        ]
    elif mode == RUN:
        rows = [
            (ADVANCE, f"EXECUTA: {run_effect}"),
            (NAV, "mudam de linha"),
            (CANCEL, "cancelar e fechar (nada e feito)"),
        ]
    elif mode == PICKER:
        rows = [
            (ADVANCE, "ESCOLHE esta OSI e volta ao formulario"),
            (NAV, "movem na lista"),
            (BACK, "voltar sem mudar"),
            (CTRL_C, "cancelar e fechar tudo"),
        ]
    elif mode == MENU:
        rows = [
            (ADVANCE, "ABRE a operacao em foco"),
            (NAV, "mudam de item"),
            (CANCEL, "fechar"),
        ]
    else:
        raise ValueError(f"unknown legend mode: {mode!r}")
    return "\n".join(_line(keys, effect) for keys, effect in rows)
