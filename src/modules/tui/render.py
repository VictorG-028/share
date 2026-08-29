"""
Pure text rendering for the grid form -- no ``prompt_toolkit`` import, raw
ANSI only (no color library), so output is assertable with plain ``in``
checks in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.tui.state import FormState

RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
REVERSE = "\033[7m"

_FALLBACK_HINT = "(lista nao capturada -- rode --refresh-osi-list)"


def _focused(text: str, *, is_focused: bool) -> str:
    return f"{REVERSE}{text}{RESET}" if is_focused else text


def render_text(state: "FormState") -> str:
    d = state.date
    on_row0 = state.row == 0

    day = _focused(f"{d.day:02d}", is_focused=on_row0 and state.field == 0)
    month = _focused(f"{d.month:02d}", is_focused=on_row0 and state.field == 1)
    year = _focused(f"{d.year:04d}", is_focused=on_row0 and state.field == 2)
    force_text = "ON" if d.force else "OFF"
    force = _focused(f"Force: {force_text}", is_focused=on_row0 and state.field == 3)

    date_line = f"{d.weekday_name()}   {day} / {month} / {year}   {force}"

    status = d.status()
    status_line = ""
    if status.message:
        color = {"red": RED, "yellow": YELLOW}.get(status.color, "")
        status_line = f"{color}{status.message}{RESET}"

    osi = state.osi.current()
    osi_text = _focused(osi.label, is_focused=state.row == 1)
    osi_line = f"Projeto (OSI): {osi_text}"
    if state.osi.is_fallback:
        osi_line += f"\n  {_FALLBACK_HINT}"

    save_choice = "[Y] / N" if state.save else "Y / [N]"
    save_text = _focused(save_choice, is_focused=state.row == 2)
    save_line = f"Salvar? {save_text}"

    lines = [date_line]
    if status_line:
        lines.append(status_line)
    lines += ["", osi_line, "", save_line, "", "setas: navegar/mudar valores  Enter: confirmar  Esc/Ctrl-C: cancelar"]
    return "\n".join(lines)
