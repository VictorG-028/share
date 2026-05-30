from __future__ import annotations

from datetime import time

# Fixed punch times per weekday, keyed by ``date.weekday()`` (0 = Monday).
# Tuple order: (entry, lunch_start, lunch_end, exit).
# Saturday (5) and Sunday (6) are intentionally absent -> StaticStrategy raises.
STATIC_TIMES: dict[int, tuple[time, time, time, time]] = {
    0: (time(9, 1), time(12, 5), time(13, 6), time(18, 2)),   # Monday
    1: (time(9, 2), time(12, 6), time(13, 7), time(18, 3)),   # Tuesday
    2: (time(9, 3), time(12, 7), time(13, 8), time(18, 4)),   # Wednesday
    3: (time(9, 4), time(12, 8), time(13, 9), time(18, 5)),   # Thursday
    4: (time(9, 5), time(12, 9), time(13, 10), time(18, 6)),  # Friday
}
