from __future__ import annotations

import csv
from datetime import date, datetime, time
from pathlib import Path

from models.appointment import Appointment

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_HISTORY_FILE = DATA_DIR / "history.csv"

# Columns expected on each CSV row.
_COLUMNS = ("day", "entry_time", "lunch_start", "lunch_end", "exit_time", "osi")


def _parse_time(value: str) -> time:
    """Parse ``HH:MM`` (zero padding optional, e.g. ``9:01`` or ``09:01``)."""
    return datetime.strptime(value.strip(), "%H:%M").time()


def _load_history(file: Path = DEFAULT_HISTORY_FILE) -> list[Appointment]:
    """
    Read a CSV of past appointments into a list of :class:`Appointment`.

    The history is trusted: rows are parsed but NOT validated against the
    generation rules (real punches may legitimately break them).
    """
    appointments: list[Appointment] = []
    with open(file, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            appointments.append(
                Appointment(
                    day=date.fromisoformat(row["day"].strip()),
                    entry_time=_parse_time(row["entry_time"]),
                    lunch_start=_parse_time(row["lunch_start"]),
                    lunch_end=_parse_time(row["lunch_end"]),
                    exit_time=_parse_time(row["exit_time"]),
                    osi=(row.get("osi") or "").strip(),
                )
            )
    return appointments
