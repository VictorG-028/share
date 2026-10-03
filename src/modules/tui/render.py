"""
Pure text rendering for the grid form -- no ``prompt_toolkit`` import, raw
ANSI only (no color library), so output is assertable with plain ``in``
checks in tests.

Everything the form itself draws is ASCII (see ``keys_legend`` for why); only
the OSI labels, which come from the site, may carry accents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modules.tui.keys_legend import OSI, PICKER, RUN, VALUE, legend

if TYPE_CHECKING:
    from modules.tui.state import FormState

RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
REVERSE = "\033[7m"

_FALLBACK_HINT = "(lista nao capturada -- use 'Atualizar lista de OSI' no menu)"

#: What the "Acao" line says and what the final button is called for each --
#: the button names the consequence, so pressing it is never a surprise.
ACTION_FILL = "So preencher (nao grava)"
ACTION_SAVE = "GRAVAR no SSG"
BUTTON_FILL = "[ PREENCHER no site (nao grava) ]"
BUTTON_SAVE = "[ GRAVAR no SSG ]"
#: Kept short: with the key column they must fit an 80-column console.
RUN_EFFECT_FILL = "PREENCHER, sem gravar, e fechar"
RUN_EFFECT_SAVE = "GRAVAR e fechar, sem outra pergunta"

#: How many rows of the list are on screen at once, and how wide a label may
#: get before it is cut. Both are about a default Windows console, which is
#: where the .exe actually runs.
PICKER_ROWS = 12
LABEL_WIDTH = 110

_LABEL_COLUMN = 7  # "Force" + room: the values line up in one column


def _focused(text: str, *, is_focused: bool) -> str:
    return f"{REVERSE}{text}{RESET}" if is_focused else text


def _ellipsize(text: str, limit: int = LABEL_WIDTH) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _row(label: str, value: str, *, is_focused: bool, width: int = _LABEL_COLUMN) -> str:
    """``> Label    value`` -- the marker survives consoles that drop reverse video."""
    marker = ">" if is_focused else " "
    return f"{marker} {label:<{width}} {value}"


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
    lines += ["", legend(PICKER)]
    return "\n".join(lines)


def render_text(state: "FormState") -> str:
    if state.osi.picking:
        return render_picker(state)

    d = state.date
    name = state.focus_name()

    def on(field: str) -> bool:
        return name == field

    day = _row(
        "Dia",
        f"{_focused(f'{d.day:02d}', is_focused=on('day'))}   {d.weekday_name()}",
        is_focused=on("day"),
    )
    month = _row("Mes", _focused(f"{d.month:02d}", is_focused=on("month")), is_focused=on("month"))
    year = _row("Ano", _focused(f"{d.year:04d}", is_focused=on("year")), is_focused=on("year"))
    force = _row(
        "Force",
        _focused("ON" if d.force else "OFF", is_focused=on("force")),
        is_focused=on("force"),
    )

    chosen = state.osi.current()
    if chosen is None:
        osi_value = f"{RED}nenhuma{RESET}\n  {_FALLBACK_HINT}"
    else:
        osi_value = _focused(_ellipsize(chosen.label), is_focused=on("osi"))
        if state.osi.is_fallback:
            osi_value += f"\n  {_FALLBACK_HINT}"
    osi = _row("OSI", osi_value, is_focused=on("osi"))

    action_text = ACTION_SAVE if state.save else ACTION_FILL
    action = _row("Acao", _focused(action_text, is_focused=on("action")), is_focused=on("action"))

    button_text = BUTTON_SAVE if state.save else BUTTON_FILL
    button_color = RED if state.save else ""
    button = _focused(f"{button_color}{button_text}{RESET if button_color else ''}", is_focused=on("run"))
    run = f"{'>' if on('run') else ' '} {button}"

    lines = ["Apontar", "", day, month, year, force]
    status = d.status()
    # A blocked day is reported once, next to the button that it blocks; the
    # note under the date is only for what does not block (today's heads-up).
    if status.message and not status.blocked:
        lines.append(f"  {status.message}")
    lines += [osi, action, "", run]
    reason = state.block_reason()
    if reason:
        color = {"red": RED, "yellow": YELLOW}.get(status.color if status.blocked else "red", RED)
        lines.append(f"  {color}Bloqueado: {reason}{RESET}")

    if on("run"):
        mode = RUN
    elif on("osi"):
        mode = OSI
    else:
        mode = VALUE
    run_effect = RUN_EFFECT_SAVE if state.save else RUN_EFFECT_FILL
    lines += ["", legend(mode, run_effect=run_effect)]
    return "\n".join(lines)
