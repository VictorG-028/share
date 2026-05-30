from datetime import date, time
from pathlib import Path

from models.appointment import Appointment
from modules.history.loader import DATA_DIR, _load_history
from modules.validation.validator import validate_list

CLEAN = DATA_DIR / "history.csv"
MESSY = DATA_DIR / "history_messy.csv"


def test_loads_three_weeks_of_weekdays():
    history = _load_history(CLEAN)
    assert len(history) == 15
    assert all(isinstance(a, Appointment) for a in history)
    # all entries are weekdays (Mon-Fri)
    assert all(a.week_day < 5 for a in history)


def test_parses_fields_correctly():
    history = _load_history(CLEAN)
    first = history[0]
    assert first.day == date(2026, 5, 11)
    assert first.entry_time == time(9, 1)
    assert first.lunch_start == time(12, 20)
    assert first.lunch_end == time(13, 40)
    assert first.exit_time == time(18, 5)
    assert first.osi == "OS-1001"
    # empty osi cell -> empty string
    assert history[1].osi == ""


def test_clean_history_passes_validation():
    ok, reason = validate_list(_load_history(CLEAN))
    assert ok, reason


def test_messy_history_loads_without_validation():
    # History is trusted: the loader must not reject rule-breaking rows.
    messy = _load_history(MESSY)
    assert len(messy) == 5
    # ...and it would indeed fail validation, proving load != validate.
    ok, _ = validate_list(messy)
    assert ok is False
