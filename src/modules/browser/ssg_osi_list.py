"""
The "Pesquisar OSI" screen (``#/osi/get-list``), driven by hand.

This is the **fallback** for :func:`modules.browser.ssg_api.osi_records`, not
the way in. The endpoint answers the same question in 0.65s; this screen took
60s+ when probed on 2026-09-10, greets you with an alert of its own
("Falha ao processar o servico remoto .../api/v1/users?userId=undefined"), and
its DataTables **recycles the existing ``<tr>`` elements** instead of creating
new ones -- so the marker trick that makes the timesheet filter honest does not
work here. What does work is the record counter ("Mostrar 1 ate 5 de 30
registros"), which is what the wait below reads.

It also sees less: the table has no activity name or id, so the label it can
build is ``OSI <codigo> | <projeto> | <descricao>`` rather than the composite
the "?" lists. Entries merge by number, so that only matters for an OSI no
other source ever saw.
"""

from __future__ import annotations

import json
import re
from typing import Any

from modules.browser import ssg_list_modal
from modules.browser.cdp import CdpPage
from modules.browser.ssg_screen import SsgError, alert_text, dismiss_alert

URL = "https://ssg.sysmap.com.br/index.html#/osi/get-list"
READY_SELECTOR = ".textbox-osi-profissional"

_LOAD_TIMEOUT_SECONDS = 90  # the screen is slow and inconsistent, by reputation
_READY_TIMEOUT_SECONDS = 40

#: "Mostrar 1 ate 5 de 30 registros" -- the only trustworthy "it finished"
#: signal on a table whose rows are reused in place.
_COUNTER = re.compile(r"de\s+(\d+)\s+registros", re.IGNORECASE)

_PROFESSIONAL = "document.querySelector('.textbox-osi-profissional')"
_PROFESSIONAL_HELP = (
    "(() => { const i = " + _PROFESSIONAL + "; if (!i) return null;"
    " const g = i.closest('.form-group') || i.parentElement;"
    " return g.querySelector('.button-show-items'); })()"
)
_FILTER_BUTTON = (
    "[...document.querySelectorAll('button.button-filter')]"
    ".find(b => b.getClientRects().length > 0)"
)
_COUNTER_TEXT = (
    "(() => { const el = [...document.querySelectorAll('*')]"
    ".find(e => e.children.length === 0 && /de \\d+ registros/i.test(e.textContent));"
    " return el ? el.textContent.trim() : null; })()"
)


def _rows_with_headers(page: CdpPage) -> tuple[list[str], list[list[str]]]:
    """The result table's headers and rows, read in one go."""
    payload = page.evaluate_json(
        "(() => { const tables = [...document.querySelectorAll('table')]"
        ".filter(t => t.querySelectorAll('tbody tr').length);"
        " const t = tables.sort((a, b) =>"
        " b.querySelectorAll('tbody tr').length - a.querySelectorAll('tbody tr').length)[0];"
        " if (!t) return JSON.stringify({headers: [], rows: []});"
        " const head = t.closest('.dataTables_wrapper') || t.parentElement;"
        " const headers = [...(head ? head.querySelectorAll('thead th') : t.querySelectorAll('thead th'))]"
        ".map(h => h.textContent.replace(/\\s+/g, ' ').trim());"
        " const rows = [...t.querySelectorAll('tbody tr')]"
        ".map(r => [...r.querySelectorAll('td')]"
        ".map(td => td.textContent.replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim()));"
        " return JSON.stringify({headers, rows}); })()"
    ) or {"headers": [], "rows": []}
    return payload["headers"], payload["rows"]


def read_records(page: CdpPage) -> list[dict[str, Any]]:
    """
    Drive the screen and return records shaped like the endpoint's.

    Shaped like the endpoint's on purpose: the caller builds entries with
    ``OsiEntry.from_record`` either way, so the fallback is a different road to
    the same place and not a second data model.
    """
    page.navigate(URL)
    page.wait_for(
        "document.querySelector('" + READY_SELECTOR + "')",
        timeout_seconds=_READY_TIMEOUT_SECONDS,
    )
    # The screen announces itself with a failed lookup of the current user.
    # It is noise from the site, present before we touch anything.
    if alert_text(page) is not None:
        dismiss_alert(page)

    page.click(_PROFESSIONAL_HELP)
    ssg_list_modal.wait_open(page)
    options = ssg_list_modal.rows(page)
    if len(options) != 1:
        ssg_list_modal.close(page)
        raise SsgError(
            "o '?' de Profissional ofereceu "
            f"{len(options)} opcoes ({options}); esperava exatamente uma, entao nao escolhi."
        )
    ssg_list_modal.select(page, 0)

    before = page.evaluate(_COUNTER_TEXT)
    page.click(_FILTER_BUTTON)
    counter = page.poll_until(
        "(() => { const t = " + _COUNTER_TEXT + ";"
        " return (t && t !== " + _json(before) + ") ? t : null; })()",
        timeout_seconds=_LOAD_TIMEOUT_SECONDS,
        poll_seconds=0.25,
    )
    if counter is None:
        counter = page.evaluate(_COUNTER_TEXT)
    match = _COUNTER.search(str(counter or ""))
    expected = int(match.group(1)) if match else None

    headers, rows = _rows_with_headers(page)
    if expected is not None and len(rows) < expected:
        raise SsgError(
            f"a listagem diz ter {expected} registros mas so {len(rows)} linhas "
            "estao na tela -- nao vou gravar um catalogo pela metade."
        )
    return [_as_record(headers, row) for row in rows if any(row)]


def _json(value: object) -> str:
    return json.dumps(value)


#: Table column -> the endpoint field the rest of the code already speaks.
_COLUMNS = {
    "Código": "Id",
    "Codigo": "Id",
    "Descrição": "ActivityName",
    "Descricao": "ActivityName",
    "Status": "StatusName",
    "Nome do Projeto": "ProjectName",
    "Início Estimado": "OsiActivityStartDateStr",
    "Inicio Estimado": "OsiActivityStartDateStr",
    "Término Estimado": "OsiActivityEndDateStr",
    "Termino Estimado": "OsiActivityEndDateStr",
}


def _as_record(headers: list[str], row: list[str]) -> dict[str, Any]:
    """One table row, keyed the way ``osi/get-by-parameters`` keys its objects."""
    record: dict[str, Any] = {}
    for index, header in enumerate(headers):
        field = _COLUMNS.get(header)
        if field and index < len(row) and field not in record:
            record[field] = row[index]
    # The table has no activity id; leaving it empty keeps the built label
    # honest about what this source could and could not see.
    record.setdefault("ActivityId", "")
    return record
