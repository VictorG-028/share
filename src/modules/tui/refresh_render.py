"""
Pure text rendering for the refresh screen -- raw ANSI, no color library,
so the output is assertable with plain ``in`` checks in tests.

Shares the highlight helpers with :mod:`modules.tui.render` rather than
redefining them: the two screens are one tool and must look like it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modules.tui.render import RESET, YELLOW, _focused

if TYPE_CHECKING:
    from modules.tui.refresh_state import RefreshFormState

_KEYS = (
    "setas: navegar/mudar valores  Enter: comecar  Esc/Ctrl-C: cancelar"
)
_TITLE = "Atualizar a lista de OSI (nada e gravado no site)"


def _toggle(label: str, value: bool, *, is_focused: bool) -> str:
    mark = "X" if value else " "
    return _focused(f"[{mark}] {label}", is_focused=is_focused)


def render_refresh(state: "RefreshFormState") -> str:
    from modules.tui.refresh_state import SOURCE_HINTS

    source = state.source.current()
    on_source = state.row == 0
    source_line = "Fonte: " + _focused(source, is_focused=on_source)
    hint = SOURCE_HINTS.get(source)
    hint_line = f"  {YELLOW}{hint}{RESET}" if hint else ""

    on_flags = state.row == 1
    holidays = _toggle(
        "considerar feriado", state.include_holidays, is_focused=on_flags and state.field == 0
    )
    weekends = _toggle(
        "considerar fim de semana",
        state.include_weekends,
        is_focused=on_flags and state.field == 1,
    )

    lines = [_TITLE, "", source_line]
    if hint_line:
        lines.append(hint_line)
    lines += [
        "",
        "Dia cuja lista sera lida:",
        f"  {holidays}   {weekends}",
        "",
        _KEYS,
    ]
    return "\n".join(lines)
