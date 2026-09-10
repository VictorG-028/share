"""
Live extraction of the OSI catalog from the SSG site.

The source is the "?" help button beside the OSI field on the timesheet
screen: it opens the site's generic "Listagem de Itens" modal, filled by a
plain read-only GET (confirmed with network capture on 2026-09-04 -- see
``doc/sysmap_ssg/pages/apontamento/README.md``). The list is day-dependent,
so the button is clicked on the most recent past day that already has an
appointment; today is never touched and no row is ever created. Dead ends
that came before: ``doc/sysmap_ssg/pages/listagem-de-osi/recon.md``.
"""

from __future__ import annotations

from datetime import date, timedelta

from modules.osi_catalog.entry import OsiEntry

#: How far back the screen is filtered, so some past day with an appointment
#: is on screen to click on.
LOOKBACK_DAYS = 30


def refresh_catalog(*, port: int | None = None) -> list[OsiEntry]:
    """
    Read the OSI list from the live site. Never writes anything.

    Raises the browser layer's own errors (``SsgLoginRequired``, ``SsgError``,
    ``BrowserNotFound``, ``CdpError``) so ``main.refresh_osi_list`` can report
    them. The listed text itself is never a reason to fail.
    """
    # Imported lazily: this module is reached through ``modules.osi_catalog``
    # by the browser-free TUI, which must not drag in the websocket stack.
    from modules.browser.browsers import DEFAULT_PORT
    from modules.browser.ssg_controller import SsgController, SsgError

    today = date.today()
    controller = SsgController(port=port or DEFAULT_PORT)
    try:
        controller.open()
        controller.filter_range(today - timedelta(days=LOOKBACK_DAYS), today)
        past_days = [day for day in controller.days_with_appointments() if day < today]
        if not past_days:
            raise SsgError(
                f"Nenhum apontamento nos ultimos {LOOKBACK_DAYS} dias para abrir a lista de OSI."
            )
        labels = controller.list_osi_help_items(max(past_days))
        # Whatever the site listed, verbatim. The text is free -- OSIs the
        # manager creates for the team come with no ``OSI <n>`` prefix at all
        # -- and everything the modal offers for a day is punchable that day,
        # so a row we cannot parse must never abort the capture.
        return [OsiEntry.from_label(label) for label in labels]
    finally:
        controller.close()
