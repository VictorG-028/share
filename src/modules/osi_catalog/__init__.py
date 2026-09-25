"""
OSI catalog: the list of project/activity codes the SSG timesheet accepts,
plus which one was used last.

Two separate concerns, two separate files on disk: the catalog itself
(refreshed by reading the site, read-only) and "last used" (written only by
a real save, so it reflects what actually got punched).

The catalog mixes two sources -- the day's "?" list and the OSI listing -- and
an entry says which one it came from, because they know different things:
only the first sees the OSIs a manager opened for the team, only the second
sees status and validity window. See :mod:`modules.osi_catalog.probe`.
"""

from __future__ import annotations

from modules.osi_catalog.cache import (
    load_catalog,
    load_last_used,
    load_meta,
    merge_entries,
    punchable,
    save_catalog,
    save_last_used,
)
from modules.osi_catalog.day_choice import DayPanel, eligible_days, parse_panels
from modules.osi_catalog.entry import (
    SOURCE_LISTING,
    SOURCE_TIMESHEET,
    STATUS_PUNCHABLE,
    OsiEntry,
)
from modules.osi_catalog.probe import SOURCE_BOTH, SOURCES, RefreshResult, refresh_catalog

__all__ = [
    "DayPanel",
    "OsiEntry",
    "RefreshResult",
    "SOURCES",
    "SOURCE_BOTH",
    "SOURCE_LISTING",
    "SOURCE_TIMESHEET",
    "STATUS_PUNCHABLE",
    "eligible_days",
    "load_catalog",
    "load_last_used",
    "load_meta",
    "merge_entries",
    "parse_panels",
    "punchable",
    "refresh_catalog",
    "save_catalog",
    "save_last_used",
]
