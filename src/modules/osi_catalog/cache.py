"""
Read/write the OSI catalog and the "last used" OSI, both under
``user_data_dir()`` -- same convention ``browsers.py`` uses for
``browser.json`` (``remembered()``/``remember()``): reading swallows
``(OSError, json.JSONDecodeError)``, writing swallows ``OSError``, because
remembering is an optimisation, never a hard failure.

``catalog_file()``/``last_used_file()`` are exposed as functions (not
module-level constants) so tests can monkeypatch them the same way
``modules.history.loader.user_history_file`` already is.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from modules.osi_catalog.entry import NUMBER_NOT_CAPTURED, OsiEntry
from modules.paths import user_data_dir

CATALOG_FILE_NAME = "osi_catalog.json"
LAST_USED_FILE_NAME = "osi_last_used.json"


def catalog_file() -> Path:
    return user_data_dir() / CATALOG_FILE_NAME


def last_used_file() -> Path:
    return user_data_dir() / LAST_USED_FILE_NAME


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
            # ``label`` is the identity and must be there; ``number`` is a
            # trace and a file written by an older build may not carry it.
            OsiEntry(
                number=entry.get("number") or NUMBER_NOT_CAPTURED,
                label=entry["label"],
            )
            for entry in payload.get("entries", [])
        ]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return []


def save_catalog(entries: list[OsiEntry]) -> None:
    """Overwrite the cache. ``captured_at`` lets a human judge staleness."""
    payload = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "entries": [{"number": e.number, "label": e.label} for e in entries],
    }
    try:
        with open(catalog_file(), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except OSError:
        pass


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
