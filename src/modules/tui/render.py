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
_KEYS_FORM = (
    "setas: navegar/mudar valores  Espaco/Tab/Enter na OSI: lista  "
    "Enter: confirmar  Esc/Ctrl-C: cancelar"
)
_KEYS_PICKER = "setas: navegar  Espaco/Enter: escolher  Tab/Esc: voltar sem mudar"

#: How many rows of the list are on screen at once, and how wide a label may
#: get before it is cut. Both are about a default Windows console, which is
#: where the .exe actually runs.
PICKER_ROWS = 12
LABEL_WIDTH = 110


def _focused(text: str, *, is_focused: bool) -> str:
    return f"{REVERSE}{text}{RESET}" if is_focused else text


def _ellipsize(text: str, limit: int = LABEL_WIDTH) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def render_picker(state: "FormState") -> str:
    """The OSI list, whole, with its own cursor -- the overlay."""
    entries = state.osi.entries
    cursor = state.osi.pick_index
    # Keep the cursor in view without ever scrolling past either end.
    start = max(0, min(cursor - PICKER_ROWS // 2, len(entries) - PICKER_ROWS))
    visible = entries[start : start + PICKER_ROWS]

    lines = [f"Escolha a OSI   ({cursor + 1}/{len(entries)})", ""]
    for offset, entry in enumerate(visible):
        index = start + offset
        marker = ">" if index == cursor else " "
        lines.append(f"{marker} {_focused(_ellipsize(entry.label), is_focused=index == cursor)}")
    lines += ["", _KEYS_PICKER]
    return "\n".join(lines)


def render_text(state: "FormState") -> str:
    if state.osi.picking:
        return render_picker(state)

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

    chosen = state.osi.current()
    if chosen is None:
        osi_line = f"Projeto (OSI): {RED}nenhuma{RESET}\n  {_FALLBACK_HINT}"
    else:
        osi_text = _focused(_ellipsize(chosen.label), is_focused=state.row == 1)
        osi_line = f"Projeto (OSI): {osi_text}"
        if state.osi.is_fallback:
            osi_line += f"\n  {_FALLBACK_HINT}"

    save_choice = "[Y] / N" if state.save else "Y / [N]"
    save_text = _focused(save_choice, is_focused=state.row == 2)
    save_line = f"Salvar? {save_text}"

    lines = [date_line]
    if status_line:
        lines.append(status_line)
    lines += ["", osi_line, "", save_line, "", _KEYS_FORM]
    return "\n".join(lines)
