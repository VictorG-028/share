from datetime import date, time

import pytest

from modules.strategy import StrategyType, get_strategy
from modules.strategy.static.generator import STATIC_SETS, static_times
from modules.strategy.static.strategy import StaticStrategy
from modules.validation.validator import validate_list

MONDAY = date(2026, 5, 25)
FRIDAY = date(2026, 5, 29)
SATURDAY = date(2026, 5, 30)
SUNDAY = date(2026, 5, 31)


def test_default_strategy_is_static():
    assert get_strategy().__class__ is StaticStrategy
    assert StrategyType.STATIC is StrategyType("static")


def test_static_times_pattern():
    assert static_times(1) == (time(9, 1), time(12, 5), time(13, 6), time(18, 2))
    assert static_times(5) == (time(9, 5), time(12, 9), time(13, 10), time(18, 6))
    # set #6, the spare
    assert static_times(6) == (time(9, 6), time(12, 10), time(13, 11), time(18, 7))


@pytest.mark.parametrize("bad", [0, 7, -1, 8])
def test_static_times_rejects_out_of_range(bad):
    with pytest.raises(ValueError):
        static_times(bad)


def test_static_sets_has_six_entries():
    assert sorted(STATIC_SETS) == [1, 2, 3, 4, 5, 6]


def test_generate_for_maps_weekday_to_set():
    # Monday -> set 1
    appt = StaticStrategy().generate_for(MONDAY)
    assert (appt.entry_time, appt.lunch_start, appt.lunch_end, appt.exit_time) == static_times(1)
    assert appt.day == MONDAY
    # Friday -> set 5
    fri = StaticStrategy().generate_for(FRIDAY)
    assert (fri.entry_time, fri.lunch_start, fri.lunch_end, fri.exit_time) == static_times(5)


@pytest.mark.parametrize("weekend_day", [SATURDAY, SUNDAY])
def test_weekend_uses_spare_set_six(weekend_day):
    # No longer raises: weekends fall back to set 6.
    appt = StaticStrategy().generate_for(weekend_day)
    assert (appt.entry_time, appt.lunch_start, appt.lunch_end, appt.exit_time) == static_times(6)


def test_generate_week_returns_five_weekdays():
    week = StaticStrategy().generate_week(FRIDAY)
    assert len(week) == 5
    assert [a.week_day for a in week] == [0, 1, 2, 3, 4]


def test_static_week_obeys_the_rules():
    # Sanity: the weekday sets (1..5) pass the same rules as the random strategy.
    week = StaticStrategy().generate_week(FRIDAY)
    ok, reason = validate_list(week)
    assert ok, reason
