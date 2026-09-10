"""
What every SSG screen driver shares: the errors and the browser lifecycle.

Two design choices live here so no screen can forget them:

* **Login is never automated.** The portal asks for a Google Authenticator
  code; nothing here can or should produce one. The user signs in by hand
  once and the dedicated profile keeps the session. Landing on a login page
  raises :class:`SsgLoginRequired` instead of typing anything.
* **The browser stays up on close.** Only the CDP connection is dropped; the
  session lives in the profile, and the window may be in use by the user.
"""

from __future__ import annotations

import time as _time

from modules.browser import browsers
from modules.browser.cdp import CdpError, CdpPage, open_tab

HOST = "ssg.sysmap.com.br"
_AFTER_NAVIGATE_SECONDS = 5


class SsgError(RuntimeError):
    """The site did not behave as the probing established."""


class SsgLoginRequired(SsgError):
    """The browser is on a login page. Only a human can get past it."""


class FieldMismatch(SsgError):
    """A field did not hold the value we typed. Never save after this."""


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
            self.page.navigate(self.url)
            _time.sleep(_AFTER_NAVIGATE_SECONDS)

        self.require_session()
        self.page.wait_for("document.querySelector('" + self.ready_selector + "')")

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
