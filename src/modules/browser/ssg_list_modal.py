"""
The site's generic "Listagem de Itens" modal.

Every "?" beside a field opens the same widget -- the OSI field on the
timesheet screen, Profissional/Projeto/Requisito/Atividade on the OSI form.
It is read-only (a single GET, confirmed with network capture on 2026-09-04);
its rows arrive by AJAX after the modal is already visible, and each row's
"select" button fills the field and closes the modal by itself.
"""

from __future__ import annotations

import time as _time

from modules.browser.cdp import CdpPage, ElementNotFound
from modules.browser.ssg_screen import SsgError

MODAL = (
    "[...document.querySelectorAll('.modal.modal-list-items')]"
    ".find(m => m.getClientRects().length > 0)"
)
#: The same modal, but only once Bootstrap has finished showing it. ``in`` is
#: added when the fade starts, so the class alone is not enough -- clicking
#: mid-fade is what makes "Fechar" no-op (measured 2026-09-09), hence the
#: settle in :func:`wait_open`.
_SHOWN = (
    "[...document.querySelectorAll('.modal.modal-list-items')]"
    ".find(m => m.getClientRects().length > 0 && m.classList.contains('in'))"
)
_CLOSE = (
    "(() => { const m = " + MODAL + "; if (!m) return null;"
    " return [...m.querySelectorAll('button, a.btn')]"
    ".find(b => b.textContent.trim() === 'Fechar' && b.getClientRects().length > 0) || null; })()"
)

OPEN_SECONDS = 10
ROWS_SECONDS = 8  # after this, an empty list is taken as the answer
#: Bootstrap's own fade is .3s; clicking inside the modal before it lands is
#: silently ignored by the widget.
FADE_SECONDS = 0.5
#: How long a click is given to actually make the modal go away.
CLOSE_SECONDS = 6


def wait_open(page: CdpPage) -> None:
    """Wait until the modal is not just present but done opening."""
    try:
        page.wait_for(_SHOWN, timeout_seconds=OPEN_SECONDS)
    except ElementNotFound as error:
        raise SsgError("O botao '?' nao abriu a lista de itens." + _frozen_hint(page)) from error
    _time.sleep(FADE_SECONDS)


def is_open(page: CdpPage) -> bool:
    return bool(page.evaluate("!!(" + MODAL + ")"))


def _wait_closed(page: CdpPage) -> bool:
    """``True`` once the modal is gone; ``False`` if it never went away."""
    deadline = _time.monotonic() + CLOSE_SECONDS
    while _time.monotonic() < deadline:
        if not is_open(page):
            return True
        _time.sleep(0.25)
    return not is_open(page)


def rows(page: CdpPage) -> list[str]:
    """The listed labels once they arrive; ``[]`` if none show up in time."""
    deadline = _time.monotonic() + ROWS_SECONDS
    while True:
        found = page.evaluate_json(
            "(() => { const m = " + MODAL + "; if (!m) return '[]';"
            " return JSON.stringify([...m.querySelectorAll('tbody tr.dynamic td.col-item')]"
            ".map(td => td.textContent.trim()).filter(Boolean)); })()"
        )
        if found or _time.monotonic() >= deadline:
            return found
        _time.sleep(0.25)


def select(page: CdpPage, index: int) -> None:
    """Click row ``index``'s select button; the site fills the field and closes."""
    page.click(
        "(() => { const m = " + MODAL + "; if (!m) return null;"
        " const tr = [...m.querySelectorAll('tbody tr.dynamic')][" + str(index) + "];"
        " return tr ? tr.querySelector('button.button-select') : null; })()"
    )
    if not _wait_closed(page):
        raise SsgError("A lista de itens nao fechou depois de selecionar." + _frozen_hint(page))
    _time.sleep(FADE_SECONDS)  # let the field the site just filled settle


def close(page: CdpPage) -> None:
    """Click "Fechar"; a modal left open would swallow the next click."""
    try:
        page.click(_CLOSE)
    except ElementNotFound:
        return
    if not _wait_closed(page):
        raise SsgError("A lista de itens nao fechou depois de clicar em Fechar." + _frozen_hint(page))


def _frozen_hint(page: CdpPage) -> str:
    """
    Name the usual suspect when a modal refuses to open or close.

    A minimised or fully covered window makes Chromium report the page as
    hidden, and CSS transitions stop running -- the site's Bootstrap modal
    then never finishes opening or closing, and its "Fechar" looks broken
    while the click is in fact landing on the button (measured 2026-09-09).
    ``browsers.launch`` passes the flags that prevent it, so this only
    happens against a browser someone else started.
    """
    try:
        hidden = bool(page.evaluate("document.hidden"))
    except Exception:  # noqa: BLE001 - a hint must never mask the real error
        return ""
    if not hidden:
        return ""
    return (
        " A aba esta congelada (janela minimizada ou coberta): as animacoes do"
        " site nao rodam. Feche este navegador para a ferramenta subir um novo,"
        " ou deixe a janela visivel."
    )


def match_row(rows: list[str], selector: str) -> int:
    """
    Index of ``selector`` in ``rows``: exact first, then a unique substring.

    Ambiguity raises instead of picking one -- on a timekeeping site the wrong
    row is worse than no row. Both screens that select from this widget go
    through here, so "how a label is matched" has one definition.
    """
    if selector in rows:
        return rows.index(selector)
    hits = [i for i, row in enumerate(rows) if selector.lower() in row.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise ValueError(f"{selector!r} nao esta entre as opcoes: {rows}")
    raise ValueError(f"{selector!r} e ambiguo entre: {[rows[i] for i in hits]}")
