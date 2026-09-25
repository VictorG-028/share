"""
The site's own service layer, called the way the site calls it.

Read from the live page's ``services.runWebMethod`` on 2026-09-10::

    var url = this.baseUrl + '/api';
    if (SysMap.getCookie('AspSession') != null) url += '/' + SysMap.getCookie('AspSession');
    $.post(url + '/' + controller + '/' + method,
           {data: jsonData, currentPage: encodeURIComponent(window.location.hash)}, cb);

Three consequences the whole module rests on:

* **The opaque ``<id>`` in ``/api/<id>/`` is the ``AspSession`` cookie.** It can
  be read straight from ``document.cookie`` -- no need to sniff a request to
  learn it, which is what the first implementation of this would have done.
* **Every call goes through the page**, because the session is a cookie in the
  browser profile; see :meth:`CdpPage.fetch_json`.
* **The answer is an envelope**, not the data: ``ReturnCode`` ``1001`` means
  success and ``ReturnObject`` holds the payload. ``INVALID_TOKEN*`` means the
  session died (the site itself redirects to the login page when it sees it).

Why this exists at all: both lists the catalog needs were being read by driving
the DOM -- a modal for one, a notoriously slow screen for the other. Measured
against the real site, the same data arrives in 0.60s and 0.65s here, versus
2.3s and 60s+ through the screens, and the day's list can be read for a day
that has no appointment row (so nothing has to be created to read it).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.parse import quote

from modules.browser.cdp import CdpError, CdpPage
from modules.browser.ssg_screen import SsgError, SsgLoginRequired

__all__ = [
    "SsgApiUnavailable",
    "logged_user",
    "osi_labels_for",
    "osi_records",
    "session_token",
]

#: The screen each call claims to come from. The site sends its own hash and
#: the server does not seem to care, but sending the real one keeps the request
#: indistinguishable from the page's.
_TIMESHEET_PAGE = "#/access-entry/get-list"
_OSI_LIST_PAGE = "#/osi/get-list"

_OK = "1001"

#: How long to give the site to fill the professional's name in by itself.
_USER_NAME_TIMEOUT_SECONDS = 10


class SsgApiUnavailable(SsgError):
    """
    The service layer did not answer usefully -- fall back to the DOM.

    Deliberately NOT raised for an empty list: a day that offers no OSI is a
    legitimate answer (``ReturnCode`` 1001 with an empty ``ReturnObject``), and
    treating it as a failure would send the caller down the slow path for
    nothing. The caller walks to the next candidate day instead.
    """


def session_token(page: CdpPage) -> str:
    """The ``AspSession`` cookie -- the ``<id>`` segment of every API route."""
    token = page.evaluate(
        "(() => { const m = document.cookie.match(/AspSession=([^;]+)/);"
        " return m ? m[1] : null; })()"
    )
    if not token:
        raise SsgApiUnavailable(
            "cookie AspSession nao encontrado -- a sessao do site nao esta na pagina."
        )
    return str(token)


def logged_user(page: CdpPage) -> str:
    """
    The professional's name, as the timesheet filter already holds it.

    Mandatory, and checked here: the OSI endpoint answers an empty ``userName``
    with **success and zero items** (measured 2026-09-10), so sending a blank
    would quietly produce an empty catalog instead of an error.

    Takes the first ``.user-name`` that actually has a value, and waits a
    moment for one to appear. Both reasons are real: more than one view of the
    SPA carries that class (a stale, empty one is still in the DOM right after
    a route change), and the site fills the field itself shortly after the
    screen renders.
    """
    name = page.poll_until(
        "(() => { const v = [...document.querySelectorAll('.user-name')]"
        ".map(e => (e.value || '').trim()).find(Boolean); return v || null; })()",
        timeout_seconds=_USER_NAME_TIMEOUT_SECONDS,
    )
    name = " ".join(str(name or "").split())
    if not name:
        raise SsgApiUnavailable(
            "o campo Profissional esta vazio -- sem ele a API devolve lista vazia "
            "em vez de erro, entao nao da para confiar na resposta."
        )
    return name


def _unwrap(payload: Any, *, what: str) -> list[Any]:
    """The ``ReturnObject`` of a successful envelope, or raise."""
    if not isinstance(payload, dict):
        raise SsgApiUnavailable(f"{what}: resposta inesperada {payload!r:.120}")
    code = str(payload.get("ReturnCode") or "")
    if code.startswith("INVALID_TOKEN"):
        raise SsgLoginRequired(
            f"{what}: a sessao do SSG expirou ({code}). Entre a mao nesta janela "
            "(inclusive o codigo do Google Authenticator); a sessao fica salva no perfil."
        )
    if code != _OK or payload.get("IsError"):
        message = payload.get("Message") or payload.get("ErrorMessage") or code
        raise SsgApiUnavailable(f"{what}: {message}")
    items = payload.get("ReturnObject")
    if items is None:
        return []
    if not isinstance(items, list):
        raise SsgApiUnavailable(f"{what}: ReturnObject nao e uma lista ({type(items).__name__})")
    return items


def osi_labels_for(page: CdpPage, day: date, *, user_name: str | None = None) -> list[str]:
    """
    The OSI labels the site offers for ``day`` -- what the "?" modal lists.

    Same endpoint the "?" button fires (``term`` empty), so the answer is the
    same text, verbatim and in the same order. **The day matters**: the server
    filters by ``date=`` and the result really does change (2026-09-10: 17
    items; 2026-09-03: 16; 2026-08-27: 15; 2026-07-01: 4).
    """
    name = user_name or logged_user(page)
    url = (
        "/api/" + session_token(page) + "/timesheet-recording/get-osi-project-activity-by-term"
        "?current-page=" + quote(_TIMESHEET_PAGE, safe="")
        + "&term=&userName=" + quote(name, safe="")
        + "&date=" + day.strftime("%d/%m/%Y")
    )
    try:
        payload = page.fetch_json(url)
    except CdpError as error:
        raise SsgApiUnavailable(f"lista de OSI de {day.isoformat()}: {error}") from error
    labels = _unwrap(payload, what=f"lista de OSI de {day.isoformat()}")
    return [str(label) for label in labels if str(label).strip()]


def osi_records(page: CdpPage, *, user_name: str | None = None) -> list[dict[str, Any]]:
    """
    Every OSI that names you as the professional, with its status and window.

    This is exactly what the "Pesquisar OSI" screen sends when Profissional is
    filled in and "Filtrar" is clicked -- ``osiFilter.UserName`` and nothing
    else -- read from ``OsiController.getList``. Unlike the "?" list it carries
    ``StatusName`` and the real validity window
    (``OsiActivityStartDateStr``/``OsiActivityEndDateStr``), and unlike the
    screen's own table it costs 0.65s instead of a minute.

    It is not a superset of the "?" list: OSIs a manager opens for the whole
    team name someone else as the professional and do not come back here.
    """
    name = user_name or logged_user(page)
    url = "/api/" + session_token(page) + "/osi/get-by-parameters"
    form = {
        "data": json.dumps({"UserName": name}),
        # The site double-encodes this (it hands an already-encoded string to
        # jQuery, which encodes the body again); matched on purpose.
        "currentPage": quote(_OSI_LIST_PAGE, safe=""),
    }
    try:
        payload = page.fetch_json(url, method="POST", form=form)
    except CdpError as error:
        raise SsgApiUnavailable(f"listagem de OSI: {error}") from error
    records = _unwrap(payload, what="listagem de OSI")
    return [record for record in records if isinstance(record, dict)]
