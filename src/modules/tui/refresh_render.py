"""
Pure text rendering for the refresh screen -- raw ANSI, ASCII only, no color
library, so the output is assertable with plain ``in`` checks in tests.

Shares the highlight helpers with :mod:`modules.tui.render` rather than
redefining them: the two screens are one tool and must look like it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modules.tui.keys_legend import RUN, VALUE, legend
from modules.tui.render import RESET, YELLOW, _focused, _row

if TYPE_CHECKING:
    from modules.tui.refresh_state import RefreshFormState

_TITLE = "Atualizar a lista de OSI (nada e gravado no site)"
BUTTON = "[ Executar ]"
_LABEL_WIDTH = len("Fim de semana")
RUN_EFFECT = "LER a lista de OSI e fechar"


def _toggle(value: bool, *, is_focused: bool) -> str:
    return _focused(f"[{'X' if value else ' '}]", is_focused=is_focused)


def render_refresh(state: "RefreshFormState") -> str:
    from modules.tui.refresh_state import SOURCE_HINTS

    name = state.focus_name()
    source = state.source.current()
    lines = [
        _TITLE,
        "",
        _row(
            "Fonte",
            _focused(source, is_focused=name == "fonte"),
            is_focused=name == "fonte",
            width=_LABEL_WIDTH,
        ),
    ]
    hint = SOURCE_HINTS.get(source)
    if hint:
        lines.append(f"  {YELLOW}{hint}{RESET}")
    lines += [
        "",
        "  Dia cuja lista sera lida:",
        _row(
            "Feriado",
            f"{_toggle(state.include_holidays, is_focused=name == 'feriado')} considerar feriado",
            is_focused=name == "feriado",
            width=_LABEL_WIDTH,
        ),
        _row(
            "Fim de semana",
            f"{_toggle(state.include_weekends, is_focused=name == 'fim_de_semana')} "
            "considerar fim de semana",
            is_focused=name == "fim_de_semana",
            width=_LABEL_WIDTH,
        ),
        "",
        f"{'>' if name == 'run' else ' '} {_focused(BUTTON, is_focused=name == 'run')}",
        "",
        legend(RUN if name == "run" else VALUE, run_effect=RUN_EFFECT),
    ]
    return "\n".join(lines)
