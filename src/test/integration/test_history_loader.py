from datetime import date, time
from pathlib import Path

import pytest

from models.appointment import Appointment
from modules.history import loader
from modules.history.loader import DATA_DIR, _load_history, append_appointment, history_file
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


# Reading comes from the bundle; writing goes to the user's own copy, because a
# frozen build cannot write next to its modules.


@pytest.fixture
def user_copy(tmp_path, monkeypatch):
    target = tmp_path / "history.csv"
    monkeypatch.setattr(loader, "user_history_file", lambda: target)
    return target


def _punch(day: date) -> Appointment:
    return Appointment(
        day=day,
        entry_time=time(9, 3),
        lunch_start=time(12, 7),
        lunch_end=time(13, 8),
        exit_time=time(18, 4),
    )


def test_reads_the_bundled_sample_until_a_user_copy_exists(user_copy):
    assert history_file() == CLEAN
    append_appointment(_punch(date(2026, 8, 26)))
    assert history_file() == user_copy


def test_append_seeds_from_the_bundle_then_adds_the_row(user_copy):
    assert append_appointment(_punch(date(2026, 8, 26))) == user_copy
    rows = _load_history(user_copy)
    # seeded with the packaged sample, plus the new punch at the end
    assert len(rows) == len(_load_history(CLEAN)) + 1
    assert rows[-1].day == date(2026, 8, 26)


def test_append_refuses_to_record_the_same_day_twice(user_copy):
    day = _punch(date(2026, 8, 26))
    append_appointment(day)
    before = len(_load_history(user_copy))
    # A duplicate would corrupt the Rule 4 window.
    assert append_appointment(day) is None
    assert len(_load_history(user_copy)) == before
