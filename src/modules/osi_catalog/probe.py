"""
Live capture of the OSI catalog from the SSG site.

Two sources, both read-only, neither one a superset of the other:

* **apontamento** -- the list the timesheet's "?" offers for a given day. It is
  the only source that knows the OSIs a manager opened for the whole team, and
  the site filters it by day on the server, so *which* day is read matters (17
  entries for 10/09/2026 against 4 for 01/07/2026, same account, same minute).
* **listagem** -- every OSI that names you as the professional, with its status
  and its real validity window. It is the only source that knows a ``Liberado``
  OSI whose window already closed, which is exactly the one that disappears
  from the first list without explanation.

Both are read through the site's own service layer
(:mod:`modules.browser.ssg_api`) rather than by driving the screens, which is
what makes the whole refresh take seconds instead of a minute -- and what lets
the day's list be read for a day that has no appointment row at all. Driving
the DOM stays as the fallback for each, so a change to the endpoints degrades
the tool instead of breaking it.

Recon: ``doc/sysmap_ssg/api.md`` and ``doc/sysmap_ssg/pages/apontamento/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from modules.osi_catalog.cache import load_catalog, load_meta, merge_entries
from modules.osi_catalog.day_choice import eligible_days, parse_panels
from modules.osi_catalog.entry import SOURCE_LISTING, SOURCE_TIMESHEET, OsiEntry

#: How far back the timesheet screen is filtered. Two weeks is enough to find a
#: workable day even across a holiday stretch, and short enough that the filter
#: stays fast.
LOOKBACK_DAYS = 14

#: What ``source`` may be. "ambas" is the only way to get a real label and a
#: status for the same OSI in one run.
SOURCE_BOTH = "ambas"
SOURCES = (SOURCE_TIMESHEET, SOURCE_LISTING, SOURCE_BOTH)


@dataclass
class RefreshResult:
    """What a refresh captured, and how."""

    entries: list[OsiEntry]
    sources: dict = field(default_factory=dict)
    day_used: date | None = None
    fell_back: list[str] = field(default_factory=list)


def refresh_catalog(
    *,
    port: int | None = None,
    include_holidays: bool = False,
    include_weekends: bool = False,
    source: str = SOURCE_TIMESHEET,
) -> RefreshResult:
    """
    Read the OSI catalog from the live site. Never writes anything to it.

    Raises the browser layer's own errors (``SsgLoginRequired``, ``SsgError``,
    ``BrowserNotFound``, ``CdpError``) so ``main.refresh_osi_list`` can report
    them. The listed text itself is never a reason to fail.
    """
    # Imported lazily: this module is reached through ``modules.osi_catalog``
    # by the browser-free TUI, which must not drag in the websocket stack.
    from modules.browser import ssg_api
    from modules.browser.browsers import DEFAULT_PORT
    from modules.browser.ssg_controller import SsgController, SsgError

    if source not in SOURCES:
        raise ValueError(f"fonte desconhecida: {source!r} (use uma de {SOURCES})")

    controller = SsgController(port=port or DEFAULT_PORT)
    result = RefreshResult(entries=load_catalog(), sources=dict(load_meta()))
    try:
        controller.open()
        user_name = ssg_api.logged_user(controller.page)

        if source in (SOURCE_TIMESHEET, SOURCE_BOTH):
            labels, day_used, fell_back = _capture_timesheet(
                controller,
                user_name=user_name,
                include_holidays=include_holidays,
                include_weekends=include_weekends,
            )
            result.day_used = day_used
            result.entries = merge_entries(
                result.entries,
                [OsiEntry.from_label(label) for label in labels],
                source=SOURCE_TIMESHEET,
            )
            result.sources[SOURCE_TIMESHEET] = _stamp(len(labels), day=day_used)
            if fell_back:
                result.fell_back.append(SOURCE_TIMESHEET)

        if source in (SOURCE_LISTING, SOURCE_BOTH):
            records, fell_back = _capture_listing(controller, user_name=user_name)
            result.entries = merge_entries(
                result.entries,
                [OsiEntry.from_record(record) for record in records],
                source=SOURCE_LISTING,
            )
            result.sources[SOURCE_LISTING] = _stamp(len(records))
            if fell_back:
                result.fell_back.append(SOURCE_LISTING)

        if not result.entries:
            raise SsgError("Nenhuma OSI capturada.")
        return result
    finally:
        controller.close()


def _stamp(count: int, *, day: date | None = None) -> dict:
    stamp = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "count": count,
    }
    if day is not None:
        stamp["day"] = day.isoformat()
    return stamp


# --------------------------------------------------------------- apontamento


def _capture_timesheet(
    controller,
    *,
    user_name: str,
    include_holidays: bool,
    include_weekends: bool,
) -> tuple[list[str], date, bool]:
    """
    Walk the eligible days, newest first, until one offers a list.

    An empty list is a legitimate answer from the site, not a failure -- so it
    is a reason to try the next day down, not to stop. Which day actually
    answered is reported all the way up, because the catalog is only as current
    as that day.
    """
    from modules.browser.ssg_controller import SsgError

    today = date.today()
    controller.filter_range(today - timedelta(days=LOOKBACK_DAYS), today)
    panels = parse_panels(controller.days_on_screen())
    if not panels:
        raise SsgError("A tela nao trouxe nenhum dia depois de filtrar.")

    candidates = eligible_days(
        panels, include_holidays=include_holidays, include_weekends=include_weekends
    )
    if not candidates:
        raise SsgError(
            f"Nenhum dia util nos ultimos {LOOKBACK_DAYS} dias "
            "(use --incluir-feriado / --incluir-fim-de-semana se voce trabalhou neles)."
        )

    fell_back = False
    for day in candidates:
        labels, used_dom = _labels_for_day(controller, day, user_name=user_name)
        fell_back = fell_back or used_dom
        if labels:
            return labels, day, fell_back
    raise SsgError(
        "Nenhum dos dias elegiveis ofereceu OSI: "
        + ", ".join(day.isoformat() for day in candidates)
    )


def _labels_for_day(controller, day: date, *, user_name: str) -> tuple[list[str], bool]:
    """``day``'s OSI labels, by endpoint if possible and by DOM if not."""
    from modules.browser.ssg_api import SsgApiUnavailable, osi_labels_for

    try:
        return osi_labels_for(controller.page, day, user_name=user_name), False
    except SsgApiUnavailable as error:
        print(f"  (endpoint indisponivel: {error} -- abrindo a lista pela tela)")

    created = controller.ensure_appointment_row(day)
    try:
        return controller.list_osi_help_items(day), True
    finally:
        if created:
            controller.discard_appointment_row(day)
            # A discard may have had to reload the route to undo the row; the
            # filter goes with it, so put the screen back the way the next
            # candidate day expects to find it.
            today = date.today()
            controller.filter_range(today - timedelta(days=LOOKBACK_DAYS), today)


# ------------------------------------------------------------------ listagem


def _capture_listing(controller, *, user_name: str) -> tuple[list[dict], bool]:
    """Every OSI of yours, with status and window -- endpoint first, screen second."""
    from modules.browser import ssg_osi_list
    from modules.browser.ssg_api import SsgApiUnavailable, osi_records

    try:
        return osi_records(controller.page, user_name=user_name), False
    except SsgApiUnavailable as error:
        print(f"  (endpoint indisponivel: {error} -- abrindo a tela de listagem)")

    records = ssg_osi_list.read_records(controller.page)
    # Leave the tab where the rest of the tool expects it.
    controller.page.navigate(controller.url)
    controller.page.wait_for(
        "document.querySelector('" + controller.ready_selector + "')"
    )
    return records, True
