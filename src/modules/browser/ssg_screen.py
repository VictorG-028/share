"""
What every SSG screen driver shares: the errors and the browser lifecycle.

Two design choices live here so no screen can forget them:

* **Login is never automated.** The portal asks for a Google Authenticator
  code; nothing here can or should produce one. The user signs in by hand
  once and the dedicated profile keeps the session. Landing on a login page
  raises :class:`SsgLoginRequired` instead of typing anything.
* **The browser stays up on close.** Only the CDP connection is dropped; the
  session lives in the profile, and the window may be in use by the user.
* **The site's own alert is never ignored.** Every screen answers a refused
  action with a Bootbox modal that covers the page; see :func:`alert_text`.
"""

from __future__ import annotations

import time as _time

from modules.browser import browsers
from modules.browser.cdp import CdpError, CdpPage, open_tab

HOST = "ssg.sysmap.com.br"
#: Ceiling for a route change, not a fixed wait: the SPA swaps views in well
#: under a second, and the flat 5s sleep this replaced was most of what made
#: a refresh feel slow.
_NAVIGATE_TIMEOUT_SECONDS = 30

#: The site's alert modal ("Aviso! ..." / "Erro! ..."), visible ones only.
#: It is a full-screen Bootbox: while it is up, its backdrop swallows every
#: click, so a click on a button behind it lands on the backdrop and silently
#: does nothing. Measured 2026-09-10: a garbled date made the timesheet answer
#: "O campo Periodo e de preenchimento obrigatorio", and every later run
#: "filtered" without filtering because the button was never actually hit.
BOOTBOX = "[...document.querySelectorAll('.bootbox')].find(m => m.getClientRects().length)"
_BOOTBOX_BUTTON = (
    "(() => { const m = " + BOOTBOX + "; if (!m) return null;"
    " return [...m.querySelectorAll('button, a.btn')]"
    ".find(b => b.getClientRects().length) || null; })()"
)
_AFTER_DISMISS_SECONDS = 0.6


class SsgError(RuntimeError):
    """The site did not behave as the probing established."""


class SsgLoginRequired(SsgError):
    """The browser is on a login page. Only a human can get past it."""


class SsgAlert(SsgError):
    """The site refused an action with its own alert. Carries the site's words."""


class FieldMismatch(SsgError):
    """A field did not hold the value we typed. Never save after this."""


def alert_text(page: CdpPage) -> str | None:
    """The visible Bootbox's text, whitespace-collapsed, or ``None``."""
    raw = page.evaluate(
        "(() => { const m = " + BOOTBOX + "; return m ? m.textContent : null; })()"
    )
    if not raw:
        return None
    return " ".join(str(raw).split())


def dismiss_alert(page: CdpPage) -> None:
    """Click the alert's own button ("OK", or the header's "x")."""
    try:
        page.click(_BOOTBOX_BUTTON)
    except CdpError:
        return
    _time.sleep(_AFTER_DISMISS_SECONDS)


class SsgScreen:
    """
    One screen of the SSG SPA, reached by its hash route.

    Subclasses set ``url`` and ``ready_selector`` (something that only exists
    once the screen has rendered). :meth:`open` prefers a tab already on that
    route, then any SSG tab (navigating it), and only then opens a new one.
    """

    url: str = ""
    ready_selector: str = ""

    def __init__(self, *, port: int = browsers.DEFAULT_PORT) -> None:
        self.port = port
        self.browser_name: str | None = None
        self._page: CdpPage | None = None

    @property
    def page(self) -> CdpPage:
        if self._page is None:
            raise SsgError("Controller nao esta aberto -- chame open() antes.")
        return self._page

    def open(self) -> None:
        """Start (or reuse) the browser and land on this screen."""
        self.browser_name = browsers.launch(self.port)
        for url_contains, timeout in ((self.url, 3), (HOST, 3)):
            try:
                self._page = CdpPage.attach(url_contains=url_contains, port=self.port, timeout_seconds=timeout)
                break
            except CdpError:
                continue
        else:
            open_tab(self.url, port=self.port)
            self._page = CdpPage.attach(url_contains=HOST, port=self.port, timeout_seconds=25)

        route = self.url.split("#", 1)[1]
        if route not in str(self.page.evaluate("location.href")):
            self._navigate_to_route()

        self.require_session()
        self.clear_stale_alert()
        self.page.wait_for("document.querySelector('" + self.ready_selector + "')")
        self.clear_stale_overlay()

    def _navigate_to_route(self) -> None:
        """
        Go to this screen's hash route and wait for it to actually be there.

        The wait cannot simply be "is ``ready_selector`` present": these are
        hash routes in one SPA, several screens share class names (both the
        timesheet and the OSI listing have a ``.start-date``), and the outgoing
        view is still in the DOM while the new one renders. So the element
        that is there *now* is marked first, and the wait is for one that is
        not marked -- the same proof the filter uses.

        A login page is an accepted outcome of the wait, not a timeout:
        :meth:`require_session` turns it into a clear error right after.
        """
        ready = "document.querySelector('" + self.ready_selector + "')"
        self.page.evaluate(
            "(() => { const e = " + ready + ";"
            " if (e) e.setAttribute('data-aa-nav', '1'); return 1; })()"
        )
        self.page.navigate(self.url)
        self.page.poll_until(
            "!!document.querySelector('" + self.ready_selector + ":not([data-aa-nav])')"
            " || !!document.querySelector('input[type=password]')",
            timeout_seconds=_NAVIGATE_TIMEOUT_SECONDS,
        )

    # ---------------------------------------------------------------- alert

    def clear_stale_alert(self) -> str | None:
        """
        Close an alert left over from an earlier run, and say what it said.

        A leftover Bootbox makes the whole screen unclickable, so refusing to
        touch it would hand the user a tool that cannot work until they click
        "OK" by hand. Closing something the site already showed costs nothing:
        it is an acknowledgement, not an action.
        """
        text = alert_text(self.page)
        if text is None:
            return None
        print(f"  (aviso do site, de uma execucao anterior, fechado: {text})")
        dismiss_alert(self.page)
        return text

    def clear_stale_overlay(self) -> bool:
        """
        Lift the site's loading veil when it got stuck over this screen.

        ``services.runWebMethod`` raises a full-screen ``SysMap.UI.showLoading``
        veil and drops it in the response callback -- so a request that never
        came back (a navigation mid-flight is enough) leaves a black
        ``position: fixed`` div at ``z-index: 10000`` with no class of its own,
        covering everything. Every click then lands on it and does nothing,
        exactly like the alert's backdrop.

        Only acts when this screen's own field is actually covered, and lifts
        it with the site's own ``hideLoading`` rather than touching the DOM.
        """
        visible_ready = (
            "[...document.querySelectorAll('" + self.ready_selector + "')]"
            ".find(e => e.getClientRects().length > 0)"
        )
        covered = self.page.blocker(visible_ready)
        if not covered:
            return False
        print(f"  (o 'carregando' do site estava travado sobre a tela, removido: {covered})")
        self.page.evaluate(
            "(() => { try { SysMap.UI.hideLoading(); } catch (e) {} return 1; })()"
        )
        _time.sleep(_AFTER_DISMISS_SECONDS)
        return True

    def stuck_hint(self) -> str:
        """
        Name the usual suspect when the screen stops answering at all.

        Measured 2026-09-11: after a run of requests, the tab reached
        ``jQuery.active == 6`` -- six calls the server never answered -- and
        from then on **no click produced any request at all**, veil stuck, and
        a full reload did not cure it. A tab opened fresh on the same profile
        was healthy immediately, so the damage is per-tab. Without this hint
        the symptom reads as "the site is broken" and costs an afternoon.
        """
        try:
            active = self.page.evaluate(
                "typeof jQuery !== 'undefined' ? jQuery.active : 0"
            )
        except Exception:  # noqa: BLE001 - a hint must never mask the real error
            return ""
        if not isinstance(active, (int, float)) or active <= 0:
            return ""
        return (
            f" Esta aba tem {int(active)} requisicao(oes) penduradas que o servidor"
            " nunca respondeu -- nesse estado nenhum clique dispara nada e nem"
            " recarregar resolve. Feche ESTA aba do SSG e rode de novo: uma aba"
            " nova no mesmo perfil volta a funcionar."
        )

    def fail_on_alert(self, context: str) -> None:
        """
        Raise :class:`SsgAlert` if the site answered the last action with one.

        The opposite of :meth:`clear_stale_alert`: an alert that appeared in
        response to what we just did is the site refusing us, and continuing
        past it is how a "filter" silently filters nothing.
        """
        text = alert_text(self.page)
        if text is not None:
            dismiss_alert(self.page)
            raise SsgAlert(f"{context}: o site recusou -- {text}")

    def close(self) -> None:
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
                f"(inclusive o codigo do Google Authenticator) e abra {self.url}; "
                "a sessao fica salva no perfil de automacao para as proximas vezes."
            )
