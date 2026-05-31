from __future__ import annotations

from datetime import time

# The 6 memorizable static sets are numbered 1..6. 0 and 7 are intentionally
# invalid -- the system only accepts these six.
SET_NUMBERS = range(1, 7)


def static_times(n: int) -> tuple[time, time, time, time]:
    """
    The n-th memorizable static set (``n`` in 1..6), following the pattern:

        entry       = 09:0n
        lunch_start = 12:(n + 4)
        lunch_end   = 13:(n + 5)
        exit        = 18:(n + 1)

    e.g. n=1 -> 09:01 / 12:05 / 13:06 / 18:02 ; n=6 -> 09:06 / 12:10 / 13:11 / 18:07.

    Raises ``ValueError`` for any ``n`` outside 1..6 (so 0 and 7 are rejected).
    """
    if n not in SET_NUMBERS:
        raise ValueError(f"Static set number must be in 1..6, got {n!r}")
    return (
        time(9, n),
        time(12, n + 4),
        time(13, n + 5),
        time(18, n + 1),
    )


#: All six sets materialised, derived from the formula (handy for tests/iteration).
STATIC_SETS: dict[int, tuple[time, time, time, time]] = {
    n: static_times(n) for n in SET_NUMBERS
}
