"""
Live extraction of the OSI catalog from the SSG site.

**Not yet implemented.** Probing session findings (2026-08-29), recorded here
and in ``ssg_selectors.json``'s ``listaOsi`` key so the next attempt doesn't
repeat the same dead ends:

- ``#/osi/get-list`` ("Pesquisar OSI" in the nav menu) is the real listing
  route, but the link is buried in a deeply nested, collapsed menu -- it
  exists in the DOM but has zero size (invisible) until its parent submenus
  are expanded, which would need driving a long, fragile hover/click chain.
- The OSI field's "?" button (``.button-show-items``, title "Clique aqui
  para visualizar os itens associados a este campo") is **not safe** to
  click blindly: clicking it once produced a bootbox modal reading "Perfeito!
  Registros alterados com sucesso" (records changed successfully) for the
  currently-filtered day -- language that contradicts this file's own
  documented "no modal on save" behavior. A read-only check afterwards
  (``row_counts``/``read_day``) showed no duplicate rows and unchanged
  values, so nothing was corrupted, but the button's real effect is
  unconfirmed and it must not be used for a read-only catalog refresh.
- The real per-keystroke typeahead search is a plain, genuinely read-only
  GET: ``/api/<id>/timesheet-recording/get-osi-project-activity-by-term
  ?current-page=...&term=<term>&userName=<name>&date=<DD/MM/AAAA>``. Two
  problems remain before this can drive ``refresh_catalog()``:
  1. It only fires on **real** keystrokes -- confirmed at the CDP
     ``Network`` domain level that this project's synthetic
     ``Input.dispatchKeyEvent`` typing (used successfully for the masked
     time/date fields all week) never triggers it, for reasons not yet
     understood.
  2. It depends on a session/token that can expire independently of normal
     page browsing (`"ReturnCode":"INVALID_TOKEN_4"` was observed from a
     live, logged-in tab), and a plain reload does not safely refresh it --
     one reload attempt logged the session out entirely instead.

Resolving this needs a calmer session: work out why synthetic key events
don't reach this endpoint's listener (unlike the masked-input fields), or
call it directly with a *validated* fresh token/cookie pair, without
reloading a page that turns out to drop the session.
"""

from __future__ import annotations

from modules.osi_catalog.entry import OsiEntry


class OsiProbeNotImplemented(RuntimeError):
    """The live OSI-list extraction hasn't been solved yet -- see module docstring."""


def refresh_catalog(*, port: int | None = None) -> list[OsiEntry]:
    raise OsiProbeNotImplemented(
        "extracao da lista de OSI ainda nao implementada "
        "(ver TODO em modules/osi_catalog/probe.py)"
    )
