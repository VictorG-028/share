from datetime import date

import pytest

from modules.strategy import StrategyType, get_strategy
from modules.strategy.static.strategy import StaticStrategy
from modules.strategy.static.values import STATIC_TIMES
from modules.validation.validator import validate_list

MONDAY = date(2026, 5, 25)
FRIDAY = date(2026, 5, 29)
SATURDAY = date(2026, 5, 30)
SUNDAY = date(2026, 5, 31)


def test_default_strategy_is_static():
    assert get_strategy().__class__ is StaticStrategy
    assert StrategyType.STATIC is StrategyType("static")


def test_generate_for_uses_fixed_weekday_values():
    appt = StaticStrategy().generate_for(MONDAY)
    entry, lunch_start, lunch_end, exit_time = STATIC_TIMES[0]
    assert appt.day == MONDAY
    assert (appt.entry_time, appt.lunch_start, appt.lunch_end, appt.exit_time) == (
        entry,
        lunch_start,
        lunch_end,
        exit_time,
    )


def test_same_weekday_different_week_gives_same_times():
    a = StaticStrategy().generate_for(date(2026, 5, 18))  # Monday
    b = StaticStrategy().generate_for(date(2026, 5, 25))  # Monday
    assert (a.entry_time, a.lunch_start, a.lunch_end, a.exit_time) == (
        b.entry_time,
        b.lunch_start,
        b.lunch_end,
        b.exit_time,
    )
    assert a.day != b.day


@pytest.mark.parametrize("weekend_day", [SATURDAY, SUNDAY])
def test_weekend_raises_not_implemented(weekend_day):
    with pytest.raises(NotImplementedError):
        StaticStrategy().generate_for(weekend_day)


def test_generate_week_returns_five_weekdays():
    week = StaticStrategy().generate_week(FRIDAY)
    assert len(week) == 5
    assert [a.week_day for a in week] == [0, 1, 2, 3, 4]


def test_static_table_obeys_the_rules():
    # Sanity check (one-off): the hand-picked static values pass the same rules
    # the natural strategy must satisfy.
    week = StaticStrategy().generate_week(FRIDAY)
    ok, reason = validate_list(week)
    assert ok, reason
