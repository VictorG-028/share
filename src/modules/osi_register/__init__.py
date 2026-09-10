"""
Creating a new OSI on the SSG site.

The pure pieces live here (the site's rejection popup -> an activity's
accepted period; the default description; the effort that makes the form's
"por Dia Útil" read 8). Driving the form is ``flow.py``, which imports the
browser stack lazily so this package stays importable without it.
"""

from __future__ import annotations

from modules.osi_register.description import default_description
from modules.osi_register.effort import PROBE_HOURS, hours_for_eight_per_day, parse_hours
from modules.osi_register.window import ActivityWindow, parse_window

__all__ = [
    "ActivityWindow",
    "PROBE_HOURS",
    "default_description",
    "hours_for_eight_per_day",
    "parse_hours",
    "parse_window",
]
