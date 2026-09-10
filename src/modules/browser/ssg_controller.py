"""
Drives the SSG timesheet screen over CDP, in the browser already installed.

Everything here was derived by probing the real site; the recon docs at
``doc/sysmap_ssg/pages/apontamento/`` (``README.md`` narrative +
``selectors.json`` data) document the selectors and the traps, and the
constants below are the executable copy of it. If the site changes,
re-probe and update BOTH.

Two design choices are deliberate and should survive refactors:

* **Filling never saves.** :meth:`fill_appointment` types and verifies but does
  not submit; writing is :meth:`save_day`, a separate call. Every write to a
  corporate timekeeping system leaves a trace, so it must be an explicit act.
* **Login is never automated.** The portal asks for a Google Authenticator
  code; nothing here can or should produce one -- see :mod:`ssg_screen`,
  which owns the browser lifecycle for every SSG screen.
"""

from __future__ import annotations

import time as _time
from datetime import date, datetime, time
from typing import Any

from models.appointment import Appointment
from modules.browser import browsers, ssg_list_modal
from modules.browser.base import BrowserController
from modules.browser.cdp import ElementNotFound
from modules.browser.ssg_screen import FieldMismatch, SsgError, SsgLoginRequired, SsgScreen

__all__ = ["SsgController", "SsgError", "SsgLoginRequired", "FieldMismatch"]

ENTRY_URL = "https://ssg.sysmap.com.br/index.html#/access-entry/get-list"

_ACCESS_ROWS_PER_DAY = 2  # morning (entry + lunch start), afternoon (lunch end + exit)
_APPOINTMENT_ROWS_PER_DAY = 1

#: What "no note" looks like. We always leave the field empty, but the site
#: stores a bare ";" for an empty note -- days punched by hand read back the
#: same way -- so both count as untouched. Anything else was typed by someone.
_NO_NOTE = {"", ";"}

# Waits. The screen is jQuery + AJAX; these were measured against the real site.
_AFTER_FILTER_SECONDS = 8
_FILTER_TIMEOUT_SECONDS = 40  # a 30-day range renders slower than one day
_AFTER_ROW_ADD_SECONDS = 1.2
_AFTER_SAVE_SECONDS = 6

_FILTER_BUTTON = (
    "[...document.querySelectorAll('button,a,input[type=button]')]"
    ".find(b => ((b.textContent || b.value || '').trim() === 'Filtrar')"
    " && b.getClientRects().length > 0)"
)
_SAVE_BUTTON = (
    "[...document.querySelectorAll('button,a.btn')]"
    ".find(b => b.textContent.includes('Salvar dias alterados')"
    " && b.getClientRects().length > 0)"
)


# --------------------------------------------------------------------- pure


def to_digits(value: time) -> str:
    """``09:03`` -> ``0903``. Masked fields take digits, never the separator."""
    return f"{value.hour:02d}{value.minute:02d}"


def to_display(value: time) -> str:
    """``09:03`` -- what the field shows once the mask is applied."""
    return f"{value.hour:02d}:{value.minute:02d}"


def worked_hours(appointment: Appointment) -> time:
    """
    Hours actually worked: morning + afternoon, lunch excluded.

    This is what the site's "Horas" field wants, and it is derivable -- which
    is why ``Appointment`` needs no extra field for it.
    """
    intervals = appointment.get_all_intervals()
    total = intervals["morning"] + intervals["afternoon"]
    minutes = int(total.total_seconds() // 60)
    return time(hour=minutes // 60, minute=minutes % 60)


def _normalized_osi(value: Any) -> str:
    """
    The OSI field's text, whitespace-collapsed, for comparing two readings.

    The composite comes back from the server after a save re-render, not only
    from the pick; collapsing runs of spaces keeps that round trip from
    reading as a divergence while any real difference still does.
    """
    return " ".join(str(value or "").split())


def date_digits(day: date) -> str:
    """``2026-08-26`` -> ``26082026`` for the masked date filters."""
    return day.strftime("%d%m%Y")


def day_locator(day: date) -> str:
    """JS that resolves to the panel of ``day``, or undefined."""
    stamp = day.strftime("%d/%m/%Y")
    return (
        "[...document.querySelectorAll('.access-entry-day')]"
        ".find(d => d.textContent.includes('" + stamp + "'))"
    )


def _access_field(day: date, row: int, field: str) -> str:
    return (
        "[..." + day_locator(day) + ".querySelectorAll('tr.access-record-row:not(.hide)')]"
        "[" + str(row) + "].querySelector('" + field + "')"
    )


def _appointment_field(day: date, field: str) -> str:
    return (
        "[..." + day_locator(day) + ".querySelectorAll('tr.appointment-row:not(.hide)')]"
        "[0].querySelector('" + field + "')"
    )


def _visible_in_day(day: date, selector: str) -> str:
    """The VISIBLE match inside a day -- the add-row buttons swap places."""
    return (
        "[..." + day_locator(day) + ".querySelectorAll('" + selector + "')]"
        ".find(b => b.getClientRects().length > 0)"
    )


# ---------------------------------------------------------------- controller


class SsgController(SsgScreen, BrowserController):
    """
    :class:`BrowserController` for the SSG timesheet, over CDP.

    Drives Edge (falling back to Chrome) with a dedicated persistent profile;
    whichever browser answered is remembered for the next run.
    """

    url = ENTRY_URL
    ready_selector = ".start-date"

    def __init__(
        self,
        *,
        osi: str | None = None,
        port: int = browsers.DEFAULT_PORT,
    ) -> None:
        super().__init__(port=port)
        #: What to look for in the day's OSI list: the full label, or any text
        #: that matches exactly one row (a bare number still works). There is
        #: no default -- the catalog is day-dependent and a stale constant
        #: books the wrong project; ``main.punch`` resolves it or refuses.
        self.osi = osi
        #: What the site actually put in the field, read back after picking.
        #: :meth:`verify` compares against this, so a click that landed on the
        #: wrong row cannot pass.
        self.osi_selected: str | None = None

    def login(self, credentials: Any | None = None) -> None:
        """
        Never automated -- see :mod:`ssg_screen`.

        Present only to satisfy the contract; it just re-checks the session so
        a caller that follows the ABC lifecycle still gets a clear error.
        """
        self.require_session()

    # --------------------------------------------------------------- screen

    def filter_day(self, day: date) -> None:
        """Filter the screen down to ``day`` and wait for its panel."""
        self.filter_range(day, day)

    def filter_range(self, start: date, end: date) -> None:
        """Filter the screen to ``start``..``end`` and wait for ``end``'s panel."""
        for selector, day in ((".start-date", start), (".end-date", end)):
            self.page.type_masked("document.querySelector('" + selector + "')", date_digits(day))
        self.page.click(_FILTER_BUTTON)
        _time.sleep(_AFTER_FILTER_SECONDS)
        self.require_session()
        try:
            self.page.wait_for(day_locator(end), timeout_seconds=_FILTER_TIMEOUT_SECONDS)
        except ElementNotFound as error:
            raise SsgError(f"O dia {end.isoformat()} nao apareceu apos filtrar.") from error

    def days_with_appointments(self) -> list[date]:
        """Days on screen that already hold a real appointment row, oldest first."""
        stamps = self.page.evaluate_json(
            "JSON.stringify([...document.querySelectorAll('.access-entry-day')]"
            ".filter(d => d.querySelectorAll('tr.appointment-row:not(.hide)').length > 0)"
            ".map(d => (d.textContent.match(/\\d{2}\\/\\d{2}\\/\\d{4}/) || [null])[0])"
            ".filter(Boolean))"
        )
        return sorted(datetime.strptime(stamp, "%d/%m/%Y").date() for stamp in stamps)

    def row_counts(self, day: date) -> dict[str, int]:
        """How many real (non-template) rows the day currently has."""
        return self.page.evaluate_json(
            "(() => { const d = " + day_locator(day) + ";"
            " if (!d) return null;"
            " return JSON.stringify({"
            " access: d.querySelectorAll('tr.access-record-row:not(.hide)').length,"
            " appointment: d.querySelectorAll('tr.appointment-row:not(.hide)').length}); })()"
        )

    def _expand(self, day: date) -> None:
        collapsed = self.page.evaluate(
            "(() => { const d = " + day_locator(day) + ";"
            " const body = d && d.querySelector('.day-body');"
            " return !!body && getComputedStyle(body).display === 'none'; })()"
        )
        if collapsed:
            self.page.click(_visible_in_day(day, ".button-toggle-day"))
            _time.sleep(_AFTER_ROW_ADD_SECONDS)

    def ensure_rows(self, day: date) -> None:
        """
        Give the day two E/S rows and one appointment row.

        An untouched day arrives collapsed and with no rows at all -- only the
        hidden templates -- so the rows must be created before anything can be
        typed. Always click the VISIBLE add button: the empty-state one is
        replaced once the first row exists.
        """
        self._expand(day)
        for _ in range(_ACCESS_ROWS_PER_DAY + _APPOINTMENT_ROWS_PER_DAY + 2):
            counts = self.row_counts(day)
            if counts is None:
                raise SsgError(f"Painel do dia {day.isoformat()} sumiu da tela.")
            if counts["access"] >= _ACCESS_ROWS_PER_DAY and (
                counts["appointment"] >= _APPOINTMENT_ROWS_PER_DAY
            ):
                return
            if counts["access"] < _ACCESS_ROWS_PER_DAY:
                self.page.click(_visible_in_day(day, ".button-add-access-row"))
            else:
                self.page.click(_visible_in_day(day, ".button-add-appointment-row"))
            _time.sleep(_AFTER_ROW_ADD_SECONDS)
        raise SsgError(
            f"Nao consegui criar as linhas do dia {day.isoformat()} "
            f"(estado final: {self.row_counts(day)})."
        )

    def read_day(self, day: date) -> dict[str, Any]:
        """Everything we care about in a day's panel, as the page has it now."""
        return self.page.evaluate_json(
            "(() => { const d = " + day_locator(day) + ";"
            " if (!d) return null;"
            " const es = [...d.querySelectorAll('tr.access-record-row:not(.hide)')];"
            " const ap = [...d.querySelectorAll('tr.appointment-row:not(.hide)')];"
            " const val = (row, cls) => { const el = row.querySelector(cls); return el ? el.value : null; };"
            " return JSON.stringify({"
            " access: es.map(r => [val(r, '.input-clock-in'), val(r, '.input-clock-out')]),"
            " hours: ap.length ? val(ap[0], '.input-appointed-hours') : null,"
            " osi: ap.length ? val(ap[0], '.input-project-activity') : null,"
            " note: ap.length ? val(ap[0], '.input-appointment-note') : null,"
            " absence: [...d.querySelectorAll('.input-absence-allowance')].filter(c => c.checked).length"
            " }); })()"
        )

    # ------------------------------------------------------------- osi list

    def _open_osi_list(self, day: date) -> list[str]:
        """
        Click the "?" beside ``day``'s OSI field; return the rows it lists.

        Leaves the modal **open**: the caller either selects a row (filling
        the field) or closes it. Both readers of the list go through here, so
        the day-dependence is honoured the same way -- the site filters the
        list by the panel's own ``date=``.
        """
        self._expand(day)
        counts = self.row_counts(day)
        if not counts or not counts["appointment"]:
            raise SsgError(
                f"O dia {day.isoformat()} nao tem linha de apontamento para abrir a lista de OSI."
            )
        self.page.click(_appointment_field(day, ".button-show-items"))
        ssg_list_modal.wait_open(self.page)
        return ssg_list_modal.rows(self.page)

    def list_osi_help_items(self, day: date) -> list[str]:
        """
        Open the "?" beside ``day``'s OSI field and return the labels it lists.

        Read-only: the button only issues a GET (confirmed with network capture
        on 2026-09-04), but the day's rows are still compared before and after
        -- a permanent tripwire, not a one-off check. The list is
        day-dependent (the site sends ``date=``), so pass the day whose OSIs
        you want.
        """
        self._expand(day)
        before = (self.row_counts(day), self.read_day(day))
        try:
            labels = self._open_osi_list(day)
        finally:
            ssg_list_modal.close(self.page)
        after = (self.row_counts(day), self.read_day(day))
        if after != before:
            raise SsgError(
                f"O dia {day.isoformat()} mudou depois de abrir a lista de OSI: {before} -> {after}"
            )
        return labels

    # ----------------------------------------------------------------- fill

    def _type_and_check(self, locator: str, digits: str, expected: str, label: str) -> None:
        actual = self.page.type_masked(locator, digits)
        if actual != expected:
            raise FieldMismatch(f"{label}: campo ficou {actual!r}, esperava {expected!r}")

    def fill_appointment(self, appointment: Appointment) -> None:
        """
        Type a day's values and verify every field. **Does not save.**

        Raises :class:`FieldMismatch` on the first field that did not take the
        value, so a wrong day is never one click away from being written.
        """
        day = appointment.day
        self.filter_day(day)
        self.ensure_rows(day)

        fields = (
            (_access_field(day, 0, ".input-clock-in"), appointment.entry_time, "entrada"),
            (_access_field(day, 0, ".input-clock-out"), appointment.lunch_start, "inicio do almoco"),
            (_access_field(day, 1, ".input-clock-in"), appointment.lunch_end, "fim do almoco"),
            (_access_field(day, 1, ".input-clock-out"), appointment.exit_time, "saida"),
            (_appointment_field(day, ".input-appointed-hours"), worked_hours(appointment), "horas"),
        )
        for locator, value, label in fields:
            self._type_and_check(locator, to_digits(value), to_display(value), label)

        self._fill_osi(day)
        self.verify(appointment)

    def _fill_osi(self, day: date) -> None:
        """
        Pick the OSI from the field's "?" list -- never by typing.

        The typeahead is not usable as an identity: it needs a number, and the
        OSIs the manager creates for the team are listed with no number at all
        (``"coe tech - setembro - 2026 | Walber Hugo da Silva - 427465"``).
        The list is the same one ``--refresh-osi-list`` caches, filtered by
        this very day, and the site fills the field itself on select -- so the
        value can be read back and held to.
        """
        if not self.osi:
            raise SsgError("Nenhuma OSI escolhida: passe --osi.")
        rows = self._open_osi_list(day)
        try:
            index = ssg_list_modal.match_row(rows, self.osi)
        except ValueError as error:
            ssg_list_modal.close(self.page)
            raise SsgError(f"OSI de {day.isoformat()}: {error}") from error
        ssg_list_modal.select(self.page, index)
        state = self.read_day(day)
        chosen = _normalized_osi(state and state["osi"])
        if not chosen:
            raise FieldMismatch(
                f"osi: o campo ficou vazio depois de escolher {rows[index]!r}."
            )
        self.osi_selected = chosen

    def verify(self, appointment: Appointment) -> dict[str, Any]:
        """
        Check the whole day against ``appointment``; raise on any divergence.

        This is the gate that must pass before :meth:`save_day`.
        """
        day = appointment.day
        state = self.read_day(day)
        if state is None:
            raise SsgError(f"Painel do dia {day.isoformat()} nao esta na tela.")

        expected_access = [
            [to_display(appointment.entry_time), to_display(appointment.lunch_start)],
            [to_display(appointment.lunch_end), to_display(appointment.exit_time)],
        ]
        problems: list[str] = []
        if state["access"] != expected_access:
            problems.append(f"horarios {state['access']} != {expected_access}")
        if state["hours"] != to_display(worked_hours(appointment)):
            problems.append(f"horas {state['hours']!r}")
        # Exact, against what the site itself put in the field when the row was
        # picked -- a click that landed on the neighbouring row is exactly the
        # failure this screen has already produced once (2026-08-29), and a
        # prefix check would wave it through.
        if self.osi_selected is None:
            problems.append("osi nao foi escolhida")
        elif _normalized_osi(state["osi"]) != self.osi_selected:
            problems.append(f"osi {state['osi']!r} != {self.osi_selected!r}")
        if str(state["note"] or "").strip() not in _NO_NOTE:
            problems.append(f"observacao deveria ficar vazia, esta {state['note']!r}")
        if state["absence"]:
            problems.append("abono de faltas marcado")
        if problems:
            raise FieldMismatch(
                f"{day.isoformat()} divergente, NAO salvei: " + "; ".join(problems)
            )
        return state

    # ----------------------------------------------------------------- save

    def save_day(self, appointment: Appointment) -> dict[str, Any]:
        """
        Verify once more, click "Salvar dias alterados", then prove it stuck.

        The button is global: it saves every changed day on screen. The site
        gives no toast and no modal, and its "Sem registro" badge shows on
        saved days too -- so the only honest confirmation is to re-filter and
        find the rows coming back from the server.
        """
        self.verify(appointment)
        self.page.click(_SAVE_BUTTON)
        _time.sleep(_AFTER_SAVE_SECONDS)
        self.filter_day(appointment.day)
        state = self.verify(appointment)
        counts = self.row_counts(appointment.day)
        if not counts or counts["access"] < _ACCESS_ROWS_PER_DAY:
            raise SsgError(
                f"{appointment.day.isoformat()}: apos salvar o dia voltou sem as linhas."
            )
        return state
