"""Turn a finished ``FormState`` into an argv list for the existing ``cli()``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.tui.state import FormState


def build_argv(state: "FormState") -> list[str]:
    argv = ["--day", state.date.as_date().strftime("%d/%m/%Y")]
    if state.date.force:
        argv.append("--force")
    # The label, not the number: it is the identity everywhere now, and the
    # OSIs the manager opens for the team have no number to send.
    chosen = state.osi.current()
    if chosen is not None:
        argv += ["--osi", chosen.label]
    # --save already implies fill+verify in punch(); --fill would be
    # redundant on that branch. --yes because the form's own Y/N toggle
    # already served as the explicit confirmation.
    argv += ["--save", "--yes"] if state.save else ["--fill"]
    return argv
