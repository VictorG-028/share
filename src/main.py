"""
Orchestrator / entry point.

Responsibilities (the only place that wires generation to browser-driving):
  1. load the trusted history,
  2. pick a strategy via the factory (default: static),
  3. generate the appointment value(s) ONCE,
  4. skip weekends,
  5. (future) replay the *same* generated values on each BrowserController in
     separate sessions, so the two controllers can be compared on equal input.

Keeping generation and browser-driving apart is deliberate: the numbers are
produced here once and handed to whichever controller drives the site.
"""

from __future__ import annotations

from datetime import date

from modules.history.loader import DEFAULT_HISTORY_FILE, _load_history
from modules.strategy import DEFAULT_STRATEGY, StrategyType, get_strategy

WEEKEND = {5, 6}  # Saturday, Sunday


def run(
    target_day: date,
    strategy_type: StrategyType = DEFAULT_STRATEGY,
):
    """Generate the appointment for ``target_day`` using ``strategy_type``."""
    if target_day.weekday() in WEEKEND:
        print(f"{target_day.isoformat()} is a weekend -- not punching.")
        return None

    history = _load_history(DEFAULT_HISTORY_FILE)
    strategy = get_strategy(strategy_type, history=history)
    appointment = strategy.generate_for(target_day)

    print(f"[{strategy_type.value}] {target_day.isoformat()}: {appointment}")
    # Future: feed `appointment` to each BrowserController (separate sessions),
    # measuring which drives the site better.
    return appointment


if __name__ == "__main__":
    # Example: a weekday (2026-05-29 is a Friday).
    run(date(2026, 5, 29))
