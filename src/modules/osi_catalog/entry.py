"""A single selectable OSI, as offered by the SSG site."""

from __future__ import annotations

import re
from dataclasses import dataclass

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


@dataclass(frozen=True)
class OsiEntry:
    """
    ``label`` is the site's own text, taken verbatim and never validated --
    it is what identifies the OSI everywhere (``--osi``, the TUI, the pick on
    the site). ``number`` is the bare OSI number (e.g. ``"82695"``) when the
    label starts with it, and :data:`NUMBER_NOT_CAPTURED` when it does not.

    The composite the site shows for an OSI of your own (see
    ``doc/sysmap_ssg/pages/apontamento/selectors.json``'s ``formatoOsi``) is
    ``"OSI <numero> | <Projeto> | <Atividade> - <id>"``.
    """

    number: str
    label: str

    @classmethod
    def from_label(cls, label: str) -> "OsiEntry":
        """
        Build an entry from whatever the site listed. **Never raises.**

        The list is free text: refusing a row we cannot parse would throw away
        an OSI that is perfectly punchable -- everything the modal offers for a
        day is punchable that day.
        """
        text = label.strip()
        match = _LABEL_NUMBER.match(text)
        return cls(number=match.group(1) if match else NUMBER_NOT_CAPTURED, label=text)
