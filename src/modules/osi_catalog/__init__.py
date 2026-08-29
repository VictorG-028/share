"""
OSI catalog: the list of project/activity codes the SSG timesheet accepts,
plus which one was used last.

Two separate concerns, two separate files on disk: the catalog itself
(refreshed by driving the site, read-only) and "last used" (written only by
a real save, so it reflects what actually got punched).
"""

from __future__ import annotations

from modules.osi_catalog.cache import (
    load_catalog,
    load_last_used,
    save_catalog,
    save_last_used,
)
from modules.osi_catalog.entry import OsiEntry
from modules.osi_catalog.probe import refresh_catalog

__all__ = [
    "OsiEntry",
    "load_catalog",
    "save_catalog",
    "load_last_used",
    "save_last_used",
    "refresh_catalog",
]
