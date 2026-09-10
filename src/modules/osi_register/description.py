"""The generic description a new OSI gets unless the user gives one."""

from __future__ import annotations

from datetime import date

MONTH_NAMES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def default_description(start: date) -> str:
    """``"Criando OSI do mes setembro"`` -- the month the activity starts in."""
    return f"Criando OSI do mes {MONTH_NAMES[start.month - 1]}"
