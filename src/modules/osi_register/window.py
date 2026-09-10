"""The period an activity accepts, as the site reveals it in a rejection popup."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

#: "... 01/09/2026 à 30/09/2026." is what the site writes; "a"/"até" are
#: accepted too so a wording tweak on their side does not break the parser.
_WINDOW = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(?:à|a|até)\s+(\d{2}/\d{2}/\d{4})")


@dataclass(frozen=True)
class ActivityWindow:
    activity: str
    start: date
    end: date


def parse_window(text: str) -> tuple[date, date]:
    """The (start, end) a popup mentions. ``ValueError`` when it mentions none."""
    match = _WINDOW.search(text)
    if not match:
        raise ValueError(f"popup sem periodo DD/MM/AAAA a DD/MM/AAAA: {text!r}")
    start, end = (datetime.strptime(stamp, "%d/%m/%Y").date() for stamp in match.groups())
    if end < start:
        raise ValueError(f"periodo invertido no popup: {text!r}")
    return start, end
