"""
Pure text rendering for the start menu -- raw ANSI, ASCII only, no
``prompt_toolkit`` import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modules.tui.keys_legend import MENU, legend
from modules.tui.render import RED, RESET, _focused

if TYPE_CHECKING:
    from modules.tui.menu_state import MenuState

_TITLE = "auto-appointment -- o que voce quer fazer?"


def render_menu(state: "MenuState") -> str:
    from modules.tui.menu_state import ITEMS

    width = max(len(item.label) for item in ITEMS)
    lines = [_TITLE, ""]
    for index, item in enumerate(ITEMS):
        focused = index == state.focus
        marker = ">" if focused else " "
        label = _focused(f"{item.label:<{width}}", is_focused=focused)
        hint = f"{RED}{item.hint}{RESET}" if item.closed else item.hint
        lines.append(f"{marker} {label}   {hint}")
    lines += ["", legend(MENU)]
    return "\n".join(lines)
