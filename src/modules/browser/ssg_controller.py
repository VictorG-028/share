"""
Drives the SSG timesheet screen over CDP, in the browser already installed.

Everything here was derived by probing the real site; ``ssg_selectors.json``
documents the selectors and the four traps, and the constants below are the
executable copy of it. If the site changes, re-probe and update BOTH.

Two design choices are deliberate and should survive refactors:

* **Filling never saves.** :meth:`fill_appointment` types and verifies but does
  not submit; writing is :meth:`save_day`, a separate call. Every write to a
  corporate timekeeping system leaves a trace, so it must be an explicit act.
* **Login is never automated.** The portal asks for a Google Authenticator
  code; nothing here can or should produce one. The user signs in by hand once
  and the dedicated profile keeps the session. If we land on a login page we
  raise :class:`SsgLoginRequired` instead of typing anything.
"""

from __future__ import annotations

import time as _time
from datetime import date, time
from typing import Any

from models.appointment import Appointment
from modules.browser import browsers
from modules.browser.base import BrowserController
from modules.browser.cdp import CdpError, CdpPage, ElementNotFound, open_tab

ENTRY_URL = "https://ssg.sysmap.com.br/index.html#/access-entry/get-list"
HOST = "ssg.sysmap.com.br"

#: Default OSI to book against. The site wants a composite string; typing just
#: the number and picking the single typeahead hit yields the full value.
DEFAULT_OSI_NUMBER = "82695"

_ACCESS_ROWS_PER_DAY = 2  # morning (entry + lunch start), afternoon (lunch end + exit)
_APPOINTMENT_ROWS_PER_DAY = 1

#: What "no note" looks like. We always leave the field empty, but the site
#: stores a bare ";" for an empty note -- days punched by hand read back the
#: same way -- so both count as untouched. Anything else was typed by someone.
_NO_NOTE = {"", ";"}

# Waits. The screen is jQuery + AJAX; these were measured against the real site.
_AFTER_FILTER_SECONDS = 8
_AFTER_ROW_ADD_SECONDS = 1.2
_AFTER_TYPEAHEAD_SECONDS = 2.5
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
_TYPEAHEAD_ITEM = (
    "[...document.querySelectorAll('ul.typeahead.dropdown-menu li')]"
    ".find(li => li.getClientRects().length > 0)"
)


class SsgError(RuntimeError):
    """The site did not behave as the probing established."""


class SsgLoginRequired(SsgError):
    """The browser is on a login page. Only a human can get past it."""


class FieldMismatch(SsgError):
    """A field did not hold the value we typed. Never save after this."""


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


class SsgController(BrowserController):
    """
    :class:`BrowserController` for the SSG timesheet, over CDP.

    Drives Edge (falling back to Chrome) with a dedicated persistent profile;
    whichever browser answered is remembered for the next run.
    """

    def __init__(
        self,
        *,
        osi_number: str = DEFAULT_OSI_NUMBER,
        port: int = browsers.DEFAULT_PORT,
    ) -> None:
        self.osi_number = osi_number
        self.port = port
        self.browser_name: str | None = None
        self._page: CdpPage | None = None

    # ------------------------------------------------------------ lifecycle

    @property
    def page(self) -> CdpPage:
        if self._page is None:
            raise SsgError("Controller nao esta aberto -- chame open() antes.")
        return self._page

    def open(self) -> None:
        """Start (or reuse) the browser and land on the timesheet screen."""
        self.browser_name = browsers.launch(self.port)
        try:
            self._page = CdpPage.attach(url_contains=HOST, port=self.port, timeout_seconds=5)
        except CdpError:
            open_tab(ENTRY_URL, port=self.port)
            self._page = CdpPage.attach(url_contains=HOST, port=self.port, timeout_seconds=25)

        if "access-entry" not in str(self.page.evaluate("location.href")):
            self.page.navigate(ENTRY_URL)
            _time.sleep(5)

        self.require_session()
        self.page.wait_for("document.querySelector('.start-date')")

    def login(self, credentials: Any | None = None) -> None:
        """
        Never automated -- see the module docstring.

        Present only to satisfy the contract; it just re-checks the session so
        a caller that follows the ABC lifecycle still gets a clear error.
        """
        self.require_session()

    def close(self) -> None:
        """
        Drop the CDP connection. The browser stays up ON PURPOSE: killing it
        would be pointless (the session lives in the profile) and would fight
        a window the user may be using.
        """
        if self._page is not None:
            self._page.close()
            self._page = None

    def require_session(self) -> None:
        """Raise if we are looking at a login page instead of the app."""
        href = str(self.page.evaluate("location.href"))
        has_password = bool(self.page.evaluate("!!document.querySelector('input[type=password]')"))
        if "wp-login" in href or "portal.sysmap.com.br/login" in href or has_password:
            raise SsgLoginRequired(
                "O browser esta na tela de login. Entre a mao nesta janela "
                f"(inclusive o codigo do Google Authenticator) e abra {ENTRY_URL}; "
                "a sessao fica salva no perfil de automacao para as proximas vezes."
            )

    # --------------------------------------------------------------- screen

    def filter_day(self, day: date) -> None:
        """Filter the screen down to ``day`` and wait for its panel."""
        digits = date_digits(day)
        for selector in (".start-date", ".end-date"):
            self.page.type_masked("document.querySelector('" + selector + "')", digits)
        self.page.click(_FILTER_BUTTON)
        _time.sleep(_AFTER_FILTER_SECONDS)
        self.require_session()
        try:
            self.page.wait_for(day_locator(day))
        except ElementNotFound as error:
            raise SsgError(f"O dia {day.isoformat()} nao apareceu apos filtrar.") from error

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
        """Type the OSI number and pick the typeahead suggestion."""
        locator = _appointment_field(day, ".input-project-activity")
        self.page.type_masked(locator, self.osi_number)
        _time.sleep(_AFTER_TYPEAHEAD_SECONDS)
        try:
            self.page.click(_TYPEAHEAD_ITEM)
        except ElementNotFound as error:
            raise SsgError(
                f"O typeahead nao ofereceu nenhuma OSI para {self.osi_number!r}."
            ) from error
        _time.sleep(1)

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
        if not str(state["osi"] or "").startswith(f"OSI {self.osi_number}"):
            problems.append(f"osi {state['osi']!r}")
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
