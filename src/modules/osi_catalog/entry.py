"""A single selectable OSI, as offered by the SSG site."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OsiEntry:
    """
    ``number`` is the bare OSI number (e.g. ``"82695"``), the same string
    ``SsgController(osi_number=...)`` and ``--osi`` already take. ``label`` is
    the full composite the site shows once picked (see
    ``ssg_selectors.json``'s ``formatoOsi``): ``"OSI <numero> | <Projeto> |
    <Atividade> - <id>"``.
    """

    number: str
    label: str
