"""
Drives the "Cadastro de OSI" screen (``#/osi/get-form``) over CDP.

Everything here was derived by probing the real site on 2026-09-05; the
recon lives in ``doc/sysmap_ssg/pages/cadastro-de-osi/`` and the constants
below are its executable copy. Two rules learned the hard way:

* **Never leave the effort field empty on blur** -- the site pops an error
  alert. It is an AutoNumeric field that silently rejects typed digits; only
  the plugin API sets it (``autoNumeric('set')`` plus the events the form
  listens to).
* **Never press Escape on a date picker** -- it clears the field. The picker
  is closed by clicking elsewhere.

Nothing here decides *what* to create: ``modules.osi_register.flow`` does.
The only server write is :meth:`save`, and the caller owns that decision.
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass
from datetime import date

from modules.browser import ssg_list_modal
from modules.browser.cdp import ElementNotFound
from modules.browser.ssg_controller import date_digits
from modules.browser.ssg_screen import SsgError, SsgScreen

FORM_URL = "https://ssg.sysmap.com.br/index.html#/osi/get-form"

_PROFESSIONAL = "input.textbox-professional"
_PROJECT = "input.textbox-project"
_REQUIREMENT = "input.textbox-requirement"
_ACTIVITY = "input.textbox-activity"
_DESCRIPTION = "textarea.textbox-description"
_EFFORT = "input.textbox-effort-quoted"
_START = "input.textbox-estimated-start"
_END = "input.textbox-estimated-end"
_PER_DAY = "span.label-effort-business-day"
_SAVE_BUTTON = ".button-save-osi"  # an <a class="btn ...">, not a <button>

#: bootbox alerts (errors, the date rejection) -- never the list-of-items modal.
_ALERT = "[...document.querySelectorAll('.bootbox')].find(m => m.getClientRects().length > 0)"
_ALERT_OK = (
    "(() => { const m = " + _ALERT + "; if (!m) return null;"
    " return [...m.querySelectorAll('button, a.btn')].find(b => /^(ok|fechar)$/i.test(b.innerText.trim())) || null; })()"
)
#: Any other visible modal (e.g. the one asking for a second description).
_OTHER_MODAL = (
    "[...document.querySelectorAll('.modal')].find(m => m.getClientRects().length > 0"
    " && !m.classList.contains('bootbox') && !m.classList.contains('modal-list-items'))"
)

_AFTER_PICK_SECONDS = 1.0
_AFTER_SAVE_SECONDS = 12
_AFTER_DISMISS_SECONDS = 1.0


def _q(selector: str) -> str:
    return "document.querySelector('" + selector + "')"


def _help_button(input_selector: str) -> str:
    return _q(input_selector) + ".closest('.input-group').querySelector('.button-show-items')"


@dataclass(frozen=True)
class SaveOutcome:
    """What the screen showed after "Gravar": ``alert``, ``modal``, ``navigated`` or ``none``."""

    kind: str
    text: str


class SsgOsiFormController(SsgScreen):
    url = FORM_URL
    ready_selector = _SAVE_BUTTON

    # -------------------------------------------------------------- pickers

    def _pick(self, input_selector: str, label: str | None, *, single: bool) -> str:
        """Open the field's "?" and select ``label`` (or the only row)."""
        self.page.click(_help_button(input_selector))
        ssg_list_modal.wait_open(self.page)
        rows = ssg_list_modal.rows(self.page)
        if single and len(rows) != 1:
            ssg_list_modal.close(self.page)
            raise SsgError(f"Esperava uma unica opcao em {input_selector}, vieram {rows}")
        try:
            index = 0 if label is None else ssg_list_modal.match_row(rows, label)
        except ValueError as error:
            ssg_list_modal.close(self.page)
            raise SsgError(str(error)) from error
        ssg_list_modal.select(self.page, index)
        _time.sleep(_AFTER_PICK_SECONDS)
        return self.read(input_selector)

    def _list(self, input_selector: str) -> list[str]:
        self.page.click(_help_button(input_selector))
        ssg_list_modal.wait_open(self.page)
        try:
            return ssg_list_modal.rows(self.page)
        finally:
            ssg_list_modal.close(self.page)

    def pick_professional(self) -> str:
        return self._pick(_PROFESSIONAL, None, single=True)

    def list_projects(self) -> list[str]:
        return self._list(_PROJECT)

    def pick_project(self, label: str) -> str:
        return self._pick(_PROJECT, label, single=False)

    def pick_requirement(self) -> str:
        return self._pick(_REQUIREMENT, None, single=True)

    def list_activities(self) -> list[str]:
        return self._list(_ACTIVITY)

    def pick_activity(self, label: str) -> str:
        return self._pick(_ACTIVITY, label, single=False)

    # --------------------------------------------------------------- fields

    def read(self, selector: str) -> str:
        return str(self.page.evaluate("(" + _q(selector) + " || {}).value") or "").strip()

    def set_description(self, text: str) -> None:
        got = self.page.type_text(_q(_DESCRIPTION), text)
        if got != text:
            raise SsgError(f"Descricao ficou {got!r}, esperava {text!r}")

    def set_dates(self, start: date, end: date) -> None:
        for selector, day in ((_START, start), (_END, end)):
            self.page.type_masked(_q(selector), date_digits(day))
            self._close_date_picker()
            expected = day.strftime("%d/%m/%Y")
            if self.read(selector) != expected:
                raise SsgError(f"{selector} ficou {self.read(selector)!r}, esperava {expected!r}")

    def _close_date_picker(self) -> None:
        # Clicking elsewhere is the only safe way: Escape clears the field.
        self.page.click(_q(_DESCRIPTION))
        _time.sleep(0.5)

    def set_effort(self, hours: int) -> str:
        """Set "Esforço Orçado" through AutoNumeric; returns the shown value."""
        shown = self.page.evaluate(
            "(() => { const $el = jQuery(" + _q(_EFFORT) + "); $el.autoNumeric('set', '" + str(hours) + "');"
            " $el.trigger('keyup').trigger('change').trigger('focusout'); return $el.val(); })()"
        )
        _time.sleep(_AFTER_PICK_SECONDS)
        return str(shown)

    def read_effort_per_day(self) -> str:
        """The "por Dia Útil (H)" figure, raw (``"2,67"``); the caller parses."""
        return str(self.page.evaluate(_q(_PER_DAY) + ".textContent")).strip()

    # ----------------------------------------------------------------- save

    def save(self) -> SaveOutcome:
        """Click "Gravar" and report what the screen did. The one server write."""
        href_before = str(self.page.evaluate("location.href"))
        self.page.click(_q(_SAVE_BUTTON))
        return self._wait_outcome(href_before)

    def answer_second_description(self, text: str) -> SaveOutcome:
        """Fill the modal the site opens after a valid "Gravar" and confirm it."""
        textarea = "(() => { const m = " + _OTHER_MODAL + "; return m ? m.querySelector('textarea') : null; })()"
        got = self.page.type_text(textarea, text)
        if got != text:
            raise SsgError(f"Segunda descricao ficou {got!r}, esperava {text!r}")
        href_before = str(self.page.evaluate("location.href"))
        self.page.click(
            "(() => { const m = " + _OTHER_MODAL + "; if (!m) return null;"
            " return [...m.querySelectorAll('button, a.btn')]"
            ".find(b => /^gravar$/i.test(b.innerText.trim()) && b.getClientRects().length > 0) || null; })()"
        )
        return self._wait_outcome(href_before, after_modal=True)

    def _wait_outcome(self, href_before: str, *, after_modal: bool = False) -> SaveOutcome:
        deadline = _time.monotonic() + _AFTER_SAVE_SECONDS
        modal_text = ""
        while _time.monotonic() < deadline:
            alert = self.page.evaluate("(" + _ALERT + " || {innerText: null}).innerText")
            if alert:
                return SaveOutcome("alert", str(alert).strip())
            modal_text = str(self.page.evaluate("(" + _OTHER_MODAL + " || {innerText: ''}).innerText") or "").strip()
            if modal_text and not after_modal:
                return SaveOutcome("modal", modal_text)
            if after_modal and not modal_text:
                after_modal = False  # it closed; keep watching for an alert or a redirect
            href = str(self.page.evaluate("location.href"))
            if href != href_before:
                return SaveOutcome("navigated", href)
            _time.sleep(0.5)
        return SaveOutcome("modal" if modal_text else "none", modal_text)

    def read_code(self) -> str:
        """The "Código:" the screen shows ("-" until the OSI exists)."""
        return str(self.page.evaluate(
            "(() => { const g = [...document.querySelectorAll('.form-group')]"
            ".find(g => /^C.digo/.test((g.querySelector('label') || {}).innerText || ''));"
            " return g ? g.innerText.replace(/^C.digo:\\s*/, '').trim() : ''; })()"
        )).strip()

    def dismiss_alert(self) -> None:
        """Click OK on the visible bootbox alert, if any."""
        try:
            self.page.click(_ALERT_OK)
        except ElementNotFound:
            return
        _time.sleep(_AFTER_DISMISS_SECONDS)
        if self.page.evaluate("!!(" + _ALERT + ")"):
            raise SsgError("O alerta nao fechou depois de clicar em OK.")

    def dismiss_stray_alerts(self) -> None:
        for _ in range(4):
            if not self.page.evaluate("!!(" + _ALERT + ")"):
                return
            self.dismiss_alert()
