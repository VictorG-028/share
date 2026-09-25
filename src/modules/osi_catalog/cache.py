"""
Read/write the OSI catalog and the "last used" OSI, both under
``user_data_dir()`` -- same convention ``browsers.py`` uses for
``browser.json`` (``remembered()``/``remember()``): reading swallows
``(OSError, json.JSONDecodeError)``, writing swallows ``OSError``, because
remembering is an optimisation, never a hard failure.

``catalog_file()``/``last_used_file()`` are exposed as functions (not
module-level constants) so tests can monkeypatch them the same way
``modules.history.loader.user_history_file`` already is.

The catalog holds entries from **both** sources at once (see
:func:`merge_entries`), because neither sees everything: the timesheet's "?"
is the only place the OSIs a manager opened for the team show up, and the
listing is the only place any status or validity window does.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from modules.osi_catalog.entry import (
    NUMBER_NOT_CAPTURED,
    SOURCE_LISTING,
    SOURCE_TIMESHEET,
    OsiEntry,
)
from modules.paths import user_data_dir

CATALOG_FILE_NAME = "osi_catalog.json"
LAST_USED_FILE_NAME = "osi_last_used.json"


def catalog_file() -> Path:
    return user_data_dir() / CATALOG_FILE_NAME


def last_used_file() -> Path:
    return user_data_dir() / LAST_USED_FILE_NAME


def _as_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def load_catalog() -> list[OsiEntry]:
    """
    The cached catalog, or ``[]`` if it was never captured or is corrupt.

    Unlike ``browsers.remembered()`` (which returns ``None`` for "nothing
    yet"), a list consumer's natural "nothing" is an empty list -- callers
    (the TUI's spinner) never need to branch on ``None`` vs ``[]``.
    """
    path = catalog_file()
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        return [
            # ``label`` is the identity and must be there; everything else is a
            # trace, and a file written by an older build carries none of it --
            # such an entry is exactly a timesheet-sourced one with no status.
            OsiEntry(
                number=entry.get("number") or NUMBER_NOT_CAPTURED,
                label=entry["label"],
                status=entry.get("status") or None,
                source=entry.get("source") or SOURCE_TIMESHEET,
                start=_as_date(entry.get("start")),
                end=_as_date(entry.get("end")),
            )
            for entry in payload.get("entries", [])
        ]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return []


def load_meta() -> dict:
    """Per-source capture info, for a human judging staleness. ``{}`` if none."""
    path = catalog_file()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("sources", {}) or {}
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}


def save_catalog(entries: list[OsiEntry], *, sources: dict | None = None) -> None:
    """Overwrite the cache. ``captured_at`` lets a human judge staleness."""
    payload = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "sources": sources or {},
        "entries": [
            {
                "number": e.number,
                "label": e.label,
                "status": e.status,
                "source": e.source,
                "start": e.start.isoformat() if e.start else None,
                "end": e.end.isoformat() if e.end else None,
            }
            for e in entries
        ],
    }
    try:
        with open(catalog_file(), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except OSError:
        pass


def merge_entries(
    existing: list[OsiEntry], fresh: list[OsiEntry], *, source: str
) -> list[OsiEntry]:
    """
    Fold a fresh capture into the catalog: **a source only overwrites itself**.

    Running the fast source daily must not throw away the statuses the slow one
    brought last week, and vice versa. When both sources saw the same OSI (same
    number), they become one entry: the label stays the one the timesheet
    actually listed -- that string is what gets matched against the day's rows
    when filling -- and the status and window come from the listing, which is
    the only source that has them.

    That merged entry carries the timesheet as its source (its label came from
    there), so refreshing the timesheet would otherwise drop it and take the
    listing's status with it -- observed live on 2026-09-11, where a plain
    ``--fonte apontamento`` turned 24 known ``Liberado`` into 20. The status
    and window are therefore carried across by number. A **listing** refresh is
    the exception: it redefines every status, so a number it no longer returns
    must not keep the one it had.
    """
    if source == SOURCE_LISTING:
        existing = [replace(e, status=None, start=None, end=None) for e in existing]
        carried: dict[str, tuple] = {}
    else:
        carried = {
            entry.number: (entry.status, entry.start, entry.end)
            for entry in existing
            if entry.number != NUMBER_NOT_CAPTURED and entry.status is not None
        }

    combined = [entry for entry in existing if entry.source != source] + fresh

    merged: list[OsiEntry] = []
    index_of: dict[str, int] = {}
    # Timesheet entries first: that list IS the menu the site offers for the
    # chosen day, so it is the order a human expects to scroll.
    for entry in (e for e in combined if e.source == SOURCE_TIMESHEET):
        if entry.number != NUMBER_NOT_CAPTURED and entry.number in index_of:
            continue
        merged.append(entry)
        if entry.number != NUMBER_NOT_CAPTURED:
            index_of[entry.number] = len(merged) - 1

    for entry in (e for e in combined if e.source != SOURCE_TIMESHEET):
        position = index_of.get(entry.number) if entry.number != NUMBER_NOT_CAPTURED else None
        if position is None:
            if entry.number != NUMBER_NOT_CAPTURED and entry.number in index_of:
                continue
            merged.append(entry)
            if entry.number != NUMBER_NOT_CAPTURED:
                index_of[entry.number] = len(merged) - 1
            continue
        merged[position] = replace(
            merged[position], status=entry.status, start=entry.start, end=entry.end
        )

    for index, entry in enumerate(merged):
        if entry.status is None and entry.number in carried:
            status, start, end = carried[entry.number]
            merged[index] = replace(entry, status=status, start=start, end=end)
    return merged


def punchable(entries: list[OsiEntry], day: date) -> list[OsiEntry]:
    """The entries that can actually be booked on ``day``."""
    return [entry for entry in entries if entry.is_punchable(day)]


def load_last_used() -> str | None:
    """
    The OSI label from the last real save, or ``None``.

    ``osi_number`` is what files written before the catalog went free-text
    hold; it is still a valid selector (a bare number is a unique substring of
    its own row), so an old file keeps its preference instead of silently
    resetting to the top of the list.
    """
    path = last_used_file()
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload.get("osi_label") or payload.get("osi_number")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def save_last_used(label: str) -> None:
    try:
        with open(last_used_file(), "w", encoding="utf-8") as handle:
            json.dump({"osi_label": label}, handle, ensure_ascii=False)
    except OSError:
        pass


__all__ = [
    "SOURCE_LISTING",
    "SOURCE_TIMESHEET",
    "catalog_file",
    "last_used_file",
    "load_catalog",
    "load_last_used",
    "load_meta",
    "merge_entries",
    "punchable",
    "save_catalog",
    "save_last_used",
]
