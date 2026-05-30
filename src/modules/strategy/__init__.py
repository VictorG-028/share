from __future__ import annotations

from enum import Enum

from models.appointment import Appointment
from modules.strategy.base import AppointmentStrategy
from modules.strategy.natural_random.strategy import NaturalRandomStrategy
from modules.strategy.static.strategy import StaticStrategy


class StrategyType(Enum):
    STATIC = "static"
    NATURAL_RANDOM = "natural_random"


#: The strategy used by the orchestrator when none is specified.
DEFAULT_STRATEGY = StrategyType.STATIC


def get_strategy(
    strategy_type: StrategyType = DEFAULT_STRATEGY,
    *,
    history: list[Appointment] | None = None,
) -> AppointmentStrategy:
    """Factory: build the concrete strategy for ``strategy_type``.

    ``history`` is only consumed by :class:`NaturalRandomStrategy`; the static
    strategy ignores it.
    """
    if strategy_type is StrategyType.STATIC:
        return StaticStrategy()
    if strategy_type is StrategyType.NATURAL_RANDOM:
        return NaturalRandomStrategy(history or [])
    raise ValueError(f"Unknown strategy type: {strategy_type!r}")


__all__ = [
    "StrategyType",
    "DEFAULT_STRATEGY",
    "get_strategy",
    "AppointmentStrategy",
    "StaticStrategy",
    "NaturalRandomStrategy",
]
