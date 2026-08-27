"""
Orchestrator / entry point.

Responsibilities (the only place that wires generation to browser-driving):
  1. load the trusted history,
  2. pick a strategy via the factory (default: static),
  3. generate the appointment value(s) ONCE,
  4. refuse anything that is not in the past (SSG accepts only past days --
     not even today -- and ``force`` does not bypass that),
  5. skip weekends and Brazilian holidays by default (override with force=True),
  5. (future) replay the *same* generated values on each BrowserController in
     separate sessions, so the two controllers can be compared on equal input.

Keeping generation and browser-driving apart is deliberate: the numbers are
produced here once and handed to whichever controller drives the site.
"""

from __future__ import annotations

from datetime import date

from modules.history.loader import DEFAULT_HISTORY_FILE, _load_history
from modules.holiday.service import is_holiday
from modules.strategy import DEFAULT_STRATEGY, StrategyType, get_strategy

WEEKEND = {5, 6}  # Saturday, Sunday


def run(
    target_day: date,
    strategy_type: StrategyType = DEFAULT_STRATEGY,
    *,
    force: bool = False,
):
    """
    Generate the appointment for ``target_day`` using ``strategy_type``.

    Only PAST days are allowed: SSG refuses the current day and any future
    date, so generating for them would produce values the site rejects. That
    rule is hard -- ``force`` does not bypass it.

    Weekends and Brazilian holidays are skipped unless ``force=True`` (use it
    when you are actually asked to work that day -- the static strategy then
    falls back to its spare set #6 for weekend days).
    """
    if target_day >= date.today():
        print(
            f"{target_day.isoformat()} is not in the past -- SSG only accepts past "
            "days (not even today). Not generating."
        )
        return None

    if not force:
        if target_day.weekday() in WEEKEND:
            print(f"{target_day.isoformat()} is a weekend -- not punching (use force=True).")
            return None
        if is_holiday(target_day):
            print(f"{target_day.isoformat()} is a holiday -- not punching (use force=True).")
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
