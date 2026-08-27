from __future__ import annotations

import csv
import shutil
from datetime import date, datetime, time
from pathlib import Path

from models.appointment import Appointment
from modules.paths import bundle_dir, user_data_dir

# Packaged, READ-ONLY data. ``bundle_dir()`` is ``src`` in development and the
# PyInstaller extraction directory when frozen, so this one expression works
# both ways -- and a frozen build never tries to write here (that directory is
# recreated on every run).
DATA_DIR = bundle_dir() / "modules" / "history" / "data"
DEFAULT_HISTORY_FILE = DATA_DIR / "history.csv"

# Columns expected on each CSV row.
_COLUMNS = ("day", "entry_time", "lunch_start", "lunch_end", "exit_time", "osi")


def user_history_file() -> Path:
    """Where punches are appended: the user's own, writable copy."""
    return user_data_dir() / "history.csv"


def history_file() -> Path:
    """
    The history to read.

    The user's own copy wins once it exists; until then the packaged sample is
    used, so a fresh install still has something to satisfy Rule 4 against.
    """
    user = user_history_file()
    return user if user.exists() else DEFAULT_HISTORY_FILE


def _parse_time(value: str) -> time:
    """Parse ``HH:MM`` (zero padding optional, e.g. ``9:01`` or ``09:01``)."""
    return datetime.strptime(value.strip(), "%H:%M").time()


def _load_history(file: Path | None = None) -> list[Appointment]:
    """
    Read a CSV of past appointments into a list of :class:`Appointment`.

    The history is trusted: rows are parsed but NOT validated against the
    generation rules (real punches may legitimately break them).
    """
    appointments: list[Appointment] = []
    with open(file or history_file(), newline="", encoding="utf-8") as handle:
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


def append_appointment(appointment: Appointment) -> Path | None:
    """
    Record a punch that was actually written to the site.

    Without this the history never grows and Rule 4 keeps checking the same
    frozen sample forever. Returns the file written, or ``None`` if that day
    was already recorded -- appending twice would corrupt the window.
    """
    target = user_history_file()
    if not target.exists():
        # Seed from the packaged sample so the window has context from day one.
        shutil.copyfile(DEFAULT_HISTORY_FILE, target)

    if any(existing.day == appointment.day for existing in _load_history(target)):
        return None

    with open(target, "a", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(
            [
                appointment.day.isoformat(),
                f"{appointment.entry_time:%H:%M}",
                f"{appointment.lunch_start:%H:%M}",
                f"{appointment.lunch_end:%H:%M}",
                f"{appointment.exit_time:%H:%M}",
                appointment.osi,
            ]
        )
    return target
