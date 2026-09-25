"""
Minimal Chrome DevTools Protocol client.

Only what driving a form needs: run JS, click with a REAL mouse event, and type
key by key. Both of those matter on the target site and were proven necessary
by probing it (see ``doc/sysmap_ssg/pages/apontamento/`` for the recon that found this):

* ``el.click()`` does not fire its day-toggle handler -- only a real
  ``Input.dispatchMouseEvent`` does;
* its time fields are masked (``jquery.maskedinput``), so writing to ``.value``
  produces garbage. Typing ``0903`` straight into a dirty field yielded
  ``90:30``; the clearing recipe in :meth:`CdpPage.type_masked` is what makes
  it land as ``09:03``.

Transport is ``websocket-client`` (pure Python, so a PyInstaller bundle stays
trivial). The CDP HTTP endpoint is enough to list targets, but evaluating needs
the websocket.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import websocket

DEFAULT_PORT = 9222
_RECV_TIMEOUT_SECONDS = 30

# The masked-field recipe. Tuned against the real site; shorter waits dropped
# keystrokes.
_FOCUS_SETTLE_SECONDS = 0.4
_CLEAR_KEY_SECONDS = 0.15
_PER_KEY_SECONDS = 0.12

_DELETE = ("Delete", "Delete", 46)
_BACKSPACE = ("Backspace", "Backspace", 8)


class CdpError(RuntimeError):
    """Anything that went wrong talking to the browser."""


class ElementNotFound(CdpError):
    """A locator matched nothing, or matched something with no box."""


class ClickBlocked(CdpError):
    """
    Something else is on top of the element, so the click would land on it.

    This site produces such blockers twice over: its Bootbox alert, and a
    loading overlay that stays up when a request it was waiting on never
    finished. Both are invisible to a locator -- the button is found, visible
    and the right size -- and a click on them does nothing at all. Silently
    doing nothing is how a filter that never ran passed for a successful one
    (measured 2026-09-10 and again 2026-09-11), so it raises.
    """


def list_targets(port: int = DEFAULT_PORT) -> list[dict[str, Any]]:
    """Every open target (tabs, workers, extensions) on ``port``."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/list", timeout=5
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
        raise CdpError(f"Nao consegui listar as abas na porta {port}: {error}") from error


def open_tab(url: str, port: int = DEFAULT_PORT) -> dict[str, Any]:
    """Open a new tab at ``url`` and return its target."""
    quoted = urllib.parse.quote(url, safe="")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/json/new?{quoted}", method="PUT"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
        raise CdpError(f"Nao consegui abrir aba em {url}: {error}") from error


class CdpPage:
    """One attached page. Use as a context manager, or call :meth:`close`."""

    def __init__(self, websocket_url: str) -> None:
        try:
            # suppress_origin is REQUIRED: websocket-client sends an Origin
            # header by default and Chromium answers CDP handshakes carrying
            # one with 403, unless the browser was started with
            # --remote-allow-origins. Dropping the header keeps us working
            # against a browser someone else launched, and avoids telling the
            # browser to accept connections from any local page.
            self._ws = websocket.create_connection(
                websocket_url, timeout=_RECV_TIMEOUT_SECONDS, suppress_origin=True
            )
        except Exception as error:  # websocket-client raises many shapes
            raise CdpError(f"Nao consegui conectar em {websocket_url}: {error}") from error
        self._next_id = 0

    # ---------------------------------------------------------------- attach

    @classmethod
    def attach(
        cls,
        *,
        url_contains: str = "",
        port: int = DEFAULT_PORT,
        timeout_seconds: float = 20,
    ) -> "CdpPage":
        """
        Attach to the first page whose URL contains ``url_contains``.

        An exact URL match wins over a substring one, so a specific tab can be
        singled out among several on the same host.
        """
        deadline = time.monotonic() + timeout_seconds
        while True:
            pages = [t for t in list_targets(port) if t.get("type") == "page"]
            exact = [t for t in pages if t.get("url") == url_contains]
            loose = [t for t in pages if url_contains in t.get("url", "")]
            chosen = (exact or loose or [None])[0]
            if chosen:
                return cls(chosen["webSocketDebuggerUrl"])
            if time.monotonic() >= deadline:
                urls = ", ".join(t.get("url", "?") for t in pages) or "nenhuma aba"
                raise CdpError(
                    f"Nenhuma aba casa com {url_contains!r}. Abertas: {urls}"
                )
            time.sleep(0.5)

    def __enter__(self) -> "CdpPage":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass

    # ------------------------------------------------------------- protocol

    def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send one command and return its result, skipping event traffic."""
        self._next_id += 1
        message_id = self._next_id
        self._ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        deadline = time.monotonic() + _RECV_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                message = json.loads(self._ws.recv())
            except Exception as error:
                raise CdpError(f"Conexao caiu durante {method}: {error}") from error
            if message.get("id") != message_id:
                continue  # an event, or a stale reply
            if "error" in message:
                raise CdpError(f"{method} falhou: {message['error'].get('message')}")
            return message.get("result", {})
        raise CdpError(f"{method} nao respondeu em {_RECV_TIMEOUT_SECONDS}s")

    def evaluate(self, expression: str) -> Any:
        """Run JS in the page and return its value."""
        result = self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in result:
            details = result["exceptionDetails"]
            description = details.get("exception", {}).get("description") or details.get("text")
            raise CdpError(f"JS falhou: {description}")
        return result.get("result", {}).get("value")

    def evaluate_json(self, expression: str) -> Any:
        """Run JS that returns a JSON string and parse it."""
        raw = self.evaluate(expression)
        if raw is None:
            return None
        return json.loads(raw)

    # ---------------------------------------------------------------- input

    def _box(self, locator_js: str) -> dict[str, float]:
        raw = self.evaluate(
            "(() => { const el = " + locator_js + ";"
            " if (!el) return null;"
            " el.scrollIntoView({block: 'center'});"
            " const r = el.getBoundingClientRect();"
            " return JSON.stringify({x: r.left + r.width / 2, y: r.top + r.height / 2,"
            " w: r.width, h: r.height}); })()"
        )
        if not raw:
            raise ElementNotFound(f"elemento nao encontrado: {locator_js}")
        box = json.loads(raw)
        if not box["w"] or not box["h"]:
            raise ElementNotFound(f"elemento invisivel (tamanho zero): {locator_js}")
        return box

    def blocker(self, locator_js: str) -> str | None:
        """
        What is covering the element's centre, if anything. ``None`` if clear.

        Uses the page's own hit testing (``elementFromPoint``): whatever it
        returns there is what a real mouse click would reach. The element
        itself, an ancestor, or a child of it (an icon inside a button) all
        count as clear.
        """
        return self.evaluate(
            "(() => { const el = " + locator_js + "; if (!el) return null;"
            " const r = el.getBoundingClientRect();"
            " const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);"
            " if (!top || top === el || el.contains(top) || top.contains(el)) return null;"
            " const cls = typeof top.className === 'string' ? top.className : '';"
            " return (top.tagName + (cls ? '.' + cls : '')).slice(0, 120)"
            "     + ' [' + (top.getAttribute('style') || '').slice(0, 80) + ']'; })()"
        )

    def click(self, locator_js: str) -> None:
        """Click with a real mouse event. Required: ``el.click()`` is ignored."""
        box = self._box(locator_js)
        covered = self.blocker(locator_js)
        if covered:
            raise ClickBlocked(f"algo cobre o elemento e receberia o clique: {covered}")
        point = {"x": box["x"], "y": box["y"]}
        self.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "button": "none", "clickCount": 0, **point})
        for event in ("mousePressed", "mouseReleased"):
            self.send(
                "Input.dispatchMouseEvent",
                {"type": event, "button": "left", "clickCount": 1, **point},
            )

    def _key(self, key: str, code: str, virtual_key: int) -> None:
        for event in ("keyDown", "keyUp"):
            self.send(
                "Input.dispatchKeyEvent",
                {"type": event, "key": key, "code": code, "windowsVirtualKeyCode": virtual_key},
            )

    def _char(self, char: str) -> None:
        virtual_key = ord(char)
        self.send(
            "Input.dispatchKeyEvent",
            {
                "type": "keyDown",
                "text": char,
                "unmodifiedText": char,
                "key": char,
                "windowsVirtualKeyCode": virtual_key,
            },
        )
        self.send(
            "Input.dispatchKeyEvent",
            {"type": "keyUp", "key": char, "windowsVirtualKeyCode": virtual_key},
        )

    def type_text(self, locator_js: str, text: str) -> str:
        """Replace a plain field's content by typing ``text``; returns the value."""
        self.click(locator_js)
        time.sleep(_FOCUS_SETTLE_SECONDS)
        self.evaluate("(() => { const e = " + locator_js + "; e.focus(); e.select(); return 1; })()")
        self._key(*_DELETE)
        time.sleep(_CLEAR_KEY_SECONDS)
        for char in text:
            self._char(char)
            time.sleep(0.03)
        return self.evaluate("(() => { const e = " + locator_js + "; return e ? e.value : null; })()")

    def type_masked(self, locator_js: str, digits: str) -> str:
        """
        Type ``digits`` into a masked field and return the resulting value.

        The clearing step is not optional: without it the caret sits at the end
        of the old value and the mask reshuffles the input.
        """
        self.click(locator_js)
        time.sleep(_FOCUS_SETTLE_SECONDS)
        self.evaluate("(() => { const e = " + locator_js + "; e.focus(); e.select(); return 1; })()")
        for key, code, virtual_key in (_DELETE, _BACKSPACE):
            self._key(key, code, virtual_key)
            time.sleep(_CLEAR_KEY_SECONDS)
        for char in digits:
            self._char(char)
            time.sleep(_PER_KEY_SECONDS)
        return self.evaluate("(() => { const e = " + locator_js + "; return e ? e.value : null; })()")

    # ------------------------------------------------------------ lifecycle

    def navigate(self, url: str) -> None:
        self.send("Page.enable")
        self.send("Page.navigate", {"url": url})

    def reload(self, *, ignore_cache: bool = True) -> None:
        self.send("Page.enable")
        self.send("Page.reload", {"ignoreCache": ignore_cache})

    def wait_for(
        self, locator_js: str, *, timeout_seconds: float = 20, poll_seconds: float = 0.1
    ) -> None:
        """
        Block until ``locator_js`` matches a visible element.

        The poll is 100ms, not the half-second it used to be: the screen's own
        AJAX answers in ~1.3s (measured 2026-09-10), so a coarse poll spends
        more time sleeping than the site spends working.
        """
        deadline = time.monotonic() + timeout_seconds
        last: Exception | None = None
        while time.monotonic() < deadline:
            try:
                self._box(locator_js)
                return
            except (ElementNotFound, CdpError) as error:
                last = error
                time.sleep(poll_seconds)
        raise ElementNotFound(f"esperei {timeout_seconds}s por {locator_js} ({last})")

    def poll_until(
        self,
        expression_js: str,
        *,
        timeout_seconds: float = 20,
        poll_seconds: float = 0.1,
        on_tick=None,
    ) -> object:
        """
        Evaluate ``expression_js`` until it returns something truthy.

        Returns that value, or ``None`` on timeout -- "it never happened" is an
        answer the caller must be able to phrase in its own words (which day,
        which screen), so this does not raise. ``on_tick`` runs once per round
        and may raise to abort early; that is how a site alert cuts a wait
        short instead of burning the whole timeout.
        """
        deadline = time.monotonic() + timeout_seconds
        while True:
            value = self.evaluate(expression_js)
            if value:
                return value
            if on_tick is not None:
                on_tick()
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_seconds)

    # -------------------------------------------------------------- network

    def fetch_json(
        self,
        url: str,
        *,
        method: str = "GET",
        form: dict[str, str] | None = None,
        timeout_seconds: float = 30,
    ) -> Any:
        """
        Run ``fetch`` INSIDE the page and return the parsed JSON.

        Inside the page on purpose: the site's session is a cookie in the
        browser profile, so a request made from Python would be anonymous. This
        is the same call the page's own jQuery makes -- see
        :mod:`modules.browser.ssg_api` for what the site's service layer puts
        in it -- and it lets a list be read for any day without touching the
        DOM at all.
        """
        body = "null"
        if form is not None:
            body = "new URLSearchParams(" + json.dumps(form) + ")"
        expression = (
            "(async () => { const r = await fetch(" + json.dumps(url) + ", {"
            " method: " + json.dumps(method) + ", credentials: 'include',"
            + (
                " headers: {'Content-Type': 'application/x-www-form-urlencoded'},"
                " body: " + body + ","
                if form is not None
                else ""
            )
            + " }); const text = await r.text();"
            " return JSON.stringify({status: r.status, body: text}); })()"
        )
        previous = self._ws.gettimeout()
        try:
            self._ws.settimeout(timeout_seconds)
            raw = self.evaluate(expression)
        finally:
            try:
                self._ws.settimeout(previous)
            except Exception:  # noqa: BLE001 - restoring a timeout must not mask
                pass
        payload = json.loads(raw)
        if payload["status"] != 200:
            raise CdpError(f"{method} {url} respondeu HTTP {payload['status']}")
        try:
            return json.loads(payload["body"])
        except json.JSONDecodeError as error:
            raise CdpError(f"{method} {url} nao respondeu JSON: {payload['body'][:200]!r}") from error

    def screenshot(self, path: str) -> None:
        data = self.send("Page.captureScreenshot", {"format": "png"})["data"]
        with open(path, "wb") as handle:
            handle.write(base64.b64decode(data))
