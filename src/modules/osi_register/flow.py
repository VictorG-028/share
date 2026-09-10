"""
Drives the OSI form end to end, in the order the user does it by hand:
Profissional -> Projeto -> Descrição -> Requisito -> Atividade -> datas ->
esforço -> Gravar -> segunda descrição.

An activity's accepted period is not published anywhere; the site only
reveals it by rejecting a save. So :func:`discover_window` saves on purpose
with dates a year off, reads the rejection, and treats any other outcome as
an emergency (a ghost OSI may exist -- the user cancels it by hand).

The browser stack is imported lazily so ``modules.osi_register`` stays
importable without it.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from modules.osi_register.effort import (
    PROBE_HOURS,
    TARGET_PER_DAY,
    hours_for_eight_per_day,
    parse_hours,
)
from modules.osi_register.window import ActivityWindow, parse_window

if TYPE_CHECKING:
    from modules.browser.ssg_osi_form import SsgOsiFormController

WRONG_SPAN_DAYS = 365
_PER_DAY_TOLERANCE = 0.005


def open_form(port: int | None = None) -> "SsgOsiFormController":
    from modules.browser.browsers import DEFAULT_PORT
    from modules.browser.ssg_osi_form import SsgOsiFormController

    form = SsgOsiFormController(port=port or DEFAULT_PORT)
    form.open()
    form.dismiss_stray_alerts()
    return form


def prepare(form: "SsgOsiFormController", project: str, description: str) -> tuple[str, list[str]]:
    """Professional, project, requirement, a description; returns (project, activities)."""
    form.pick_professional()
    chosen = form.pick_project(project)
    form.set_description(description)
    form.pick_requirement()
    return chosen, form.list_activities()


def discover_window(form: "SsgOsiFormController", activity: str) -> ActivityWindow:
    """Save with dates a year off and read the period the site insists on."""
    from modules.browser.ssg_screen import SsgError

    form.pick_activity(activity)
    today = date.today()
    form.set_dates(today - timedelta(days=WRONG_SPAN_DAYS), today + timedelta(days=WRONG_SPAN_DAYS))
    form.set_effort(PROBE_HOURS)
    outcome = form.save()
    if outcome.kind != "alert":
        raise SsgError(
            "Gravar com datas erradas NAO foi rejeitado "
            f"({outcome.kind}: {outcome.text[:200]!r}). Confira a tela: pode ter criado uma OSI."
        )
    form.dismiss_alert()
    try:
        start, end = parse_window(outcome.text)
    except ValueError as error:
        raise SsgError(f"O site rejeitou, mas sem o periodo esperado: {outcome.text!r}") from error
    return ActivityWindow(activity, start, end)


def fill(form: "SsgOsiFormController", window: ActivityWindow, description: str) -> int:
    """
    Fill the real values without saving; returns the effort that reads 8/day.

    The site divides the effort by its own count of business days, so a probe
    fill tells that count, and a second fill lands exactly on 8 -- verified,
    never assumed.
    """
    from modules.browser.ssg_screen import SsgError

    form.pick_activity(window.activity)
    form.set_description(description)
    form.set_dates(window.start, window.end)
    form.set_effort(PROBE_HOURS)
    hours = hours_for_eight_per_day(PROBE_HOURS, parse_hours(form.read_effort_per_day()))
    form.set_effort(hours)
    per_day = parse_hours(form.read_effort_per_day())
    if abs(per_day - TARGET_PER_DAY) > _PER_DAY_TOLERANCE:
        raise SsgError(f"Esforco {hours}h deu {per_day} por dia util, esperava {TARGET_PER_DAY:g}.")
    return hours


def submit(form: "SsgOsiFormController", description: str) -> str:
    """Save for real: Gravar, second description, success. Returns what the site said."""
    from modules.browser.ssg_screen import SsgError

    outcome = form.save()
    if outcome.kind == "alert":
        form.dismiss_alert()
        raise SsgError(f"O site recusou a OSI: {outcome.text!r}")
    if outcome.kind == "modal":
        outcome = form.answer_second_description(description)
    if outcome.kind == "alert":
        text = outcome.text
        form.dismiss_alert()
        if "sucesso" not in text.lower():
            raise SsgError(f"O site respondeu com erro depois da segunda descricao: {text!r}")
        return text
    if outcome.kind == "navigated":
        return outcome.text
    raise SsgError(f"Sem sinal de sucesso depois de Gravar ({outcome.kind}: {outcome.text[:200]!r}).")
