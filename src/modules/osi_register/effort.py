"""
Budgeted effort, with the site as the only source of truth.

The form derives "Esforço Orçado por Dia Útil (H)" from "Esforço Orçado" using
its own count of business days for the period. That count is never shown, but
it is ``filled / per_day``, so one probe fill is enough to compute the total
that makes the per-day figure read exactly 8.
"""

from __future__ import annotations

PROBE_HOURS = 40
TARGET_PER_DAY = 8.0


def parse_hours(text: str) -> float:
    """``"5,00"`` (Brazilian decimal comma) or ``"5.00"`` -> ``5.0``."""
    cleaned = text.strip().replace(".", "").replace(",", ".") if "," in text else text.strip()
    try:
        return float(cleaned)
    except ValueError as error:
        raise ValueError(f"valor de horas ilegivel: {text!r}") from error


def hours_for_eight_per_day(filled_hours: float, per_day_shown: float) -> int:
    """The total that makes the per-day figure read 8, given one probe fill."""
    if per_day_shown <= 0:
        raise ValueError(f"esforco por dia util invalido: {per_day_shown!r}")
    return round(TARGET_PER_DAY * filled_hours / per_day_shown)
