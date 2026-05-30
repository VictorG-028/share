import random
from datetime import date

from modules.strategy import StrategyType, get_strategy
from modules.strategy.natural_random.strategy import NaturalRandomStrategy
from modules.validation.validator import validate, validate_list

FRIDAY = date(2026, 5, 29)


def test_factory_builds_natural_with_history():
    strategy = get_strategy(StrategyType.NATURAL_RANDOM, history=[])
    assert isinstance(strategy, NaturalRandomStrategy)


def test_generate_for_is_valid():
    random.seed(1)
    appt = NaturalRandomStrategy().generate_for(FRIDAY)
    ok, reason = validate(appt, [])
    assert ok, reason
    assert appt.day == FRIDAY


def test_generate_week_is_internally_valid():
    random.seed(2)
    week = NaturalRandomStrategy().generate_week(FRIDAY)
    assert len(week) == 5
    ok, reason = validate_list(week)
    assert ok, reason


def test_strategy_is_immutable():
    history = []
    strategy = NaturalRandomStrategy(history)
    random.seed(3)
    strategy.generate_week(FRIDAY)
    # Neither the caller's list nor the internal copy grew.
    assert history == []


def test_seed_makes_generation_reproducible():
    random.seed(42)
    first = NaturalRandomStrategy().generate_for(FRIDAY)
    random.seed(42)
    second = NaturalRandomStrategy().generate_for(FRIDAY)
    assert first == second
