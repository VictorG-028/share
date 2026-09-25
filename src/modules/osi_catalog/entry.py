"""A single selectable OSI, as offered by the SSG site."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

#: The site's composite label usually starts with the bare number:
#: ``OSI 82695 | ...``. Usually, not always -- see :data:`NUMBER_NOT_CAPTURED`.
_LABEL_NUMBER = re.compile(r"^OSI\s+(\d+)\s*\|")

#: What ``number`` holds when the label carries no ``OSI <n> |`` prefix.
#: Those are the OSIs the manager creates for the whole team (the activity is
#: someone's name), and the site lists them without a number -- e.g.
#: ``"coe tech - setembro - 2026 | Walber Hugo da Silva - 427465"``. A visible
#: sentinel, not ``None``: the field stays mandatory and the gap stays legible
#: in ``osi_catalog.json``. It is a trace, never a selector -- nothing types it
#: anywhere; picking an OSI goes by ``label``.
NUMBER_NOT_CAPTURED = "NÃO CAPTURADO"

#: Where an entry came from. The two sources see different things, so an entry
#: has to say which one it is: only the timesheet list knows the OSIs a manager
#: opened for the team, and only the listing knows any status at all.
SOURCE_TIMESHEET = "apontamento"
SOURCE_LISTING = "listagem"

#: The one status the site lets you book against. Everything else is kept
#: (that is the point of reading the listing) but never offered.
STATUS_PUNCHABLE = "Liberado"


def _parse_stamp(value: Any) -> date | None:
    """``"31/08/2026"`` -> date. Anything unparseable is simply unknown."""
    try:
        return datetime.strptime(str(value).strip(), "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class OsiEntry:
    """
    ``label`` is the site's own text, taken verbatim and never validated --
    it is what identifies the OSI everywhere (``--osi``, the TUI, the pick on
    the site). ``number`` is the bare OSI number (e.g. ``"82695"``) when the
    label starts with it, and :data:`NUMBER_NOT_CAPTURED` when it does not.

    ``status``, ``start`` and ``end`` are ``None`` for an entry read from the
    timesheet's "?" list, which does not publish them -- absence means "the
    site did not say", never "no". The composite the site shows for an OSI of
    your own (see ``doc/sysmap_ssg/pages/apontamento/selectors.json``'s
    ``formatoOsi``) is ``"OSI <numero> | <Projeto> | <Atividade> - <id>"``.
    """

    number: str
    label: str
    status: str | None = None
    source: str = SOURCE_TIMESHEET
    start: date | None = None
    end: date | None = None

    @classmethod
    def from_label(cls, label: str, *, source: str = SOURCE_TIMESHEET) -> "OsiEntry":
        """
        Build an entry from whatever the site listed. **Never raises.**

        The list is free text: refusing a row we cannot parse would throw away
        an OSI that is perfectly punchable -- everything the "?" offers for a
        day is punchable that day.
        """
        text = label.strip()
        match = _LABEL_NUMBER.match(text)
        return cls(
            number=match.group(1) if match else NUMBER_NOT_CAPTURED,
            label=text,
            source=source,
        )

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "OsiEntry":
        """
        Build an entry from one ``osi/get-by-parameters`` object.

        The label is **reconstructed**, not read: the listing has no composite
        text of its own, but the site builds the one the "?" shows out of these
        very fields, and the reconstruction was checked character for character
        against a real row (OSI 83385) on 2026-09-10. That is what lets the two
        sources merge into one catalog instead of two vocabularies.
        """
        number = str(record.get("Id") or "").strip()
        activity = str(record.get("ActivityName") or "").strip()
        activity_id = str(record.get("ActivityId") or "").strip()
        if activity_id:
            activity = f"{activity} - {activity_id}"
        label = "OSI {} | {} | {}".format(
            number, str(record.get("ProjectName") or "").strip(), activity
        )
        status = str(record.get("StatusName") or "").strip() or None
        return cls(
            number=number or NUMBER_NOT_CAPTURED,
            label=label,
            status=status,
            source=SOURCE_LISTING,
            start=_parse_stamp(record.get("OsiActivityStartDateStr")),
            end=_parse_stamp(record.get("OsiActivityEndDateStr")),
        )

    # ------------------------------------------------------------ questions

    def covers(self, day: date) -> bool:
        """Whether ``day`` falls in the OSI's validity window."""
        if self.start is not None and day < self.start:
            return False
        if self.end is not None and day > self.end:
            return False
        return True

    def is_punchable(self, day: date) -> bool:
        """
        Whether this OSI can be booked on ``day``.

        ``Liberado`` alone is not enough and this is not a theory: of the 24
        ``Liberado`` OSIs read on 2026-09-10, only 4 were valid that day. The
        82695 is the canonical case -- ``Liberado`` forever, window closed on
        30/08, and the site simply stops listing it.
        """
        if self.status is not None and self.status != STATUS_PUNCHABLE:
            return False
        return self.covers(day)
