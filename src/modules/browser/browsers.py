"""
Find, launch and remember the browser that drives the site.

We never ship a browser: the executable stays small because it drives the one
the machine already has, over CDP, using a dedicated persistent profile. That
profile is the whole login story -- the user signs in by hand once (the portal
asks for a Google Authenticator code, which nothing here can or should
generate) and the session cookie lives on in the profile.

Edge is tried first and Chrome second, ONE AT A TIME, and whichever answered is
remembered in the user data dir so the next run does not rediscover it.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from modules.paths import user_data_dir

DEFAULT_PORT = 9222
PROFILE_DIR_NAME = "AutoAppointmentProfile"
_STATE_FILE = "browser.json"
_STARTUP_TIMEOUT_SECONDS = 30
_POLL_SECONDS = 0.5

EDGE = "edge"
CHROME = "chrome"


class BrowserNotFound(RuntimeError):
    """No supported browser could be located or started."""


@dataclass(frozen=True)
class Browser:
    """A browser binary we can drive."""

    name: str
    path: Path


def _program_files() -> list[str]:
    return [
        os.environ.get("ProgramFiles", "C:/Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]


def candidates() -> list[Browser]:
    """Installed browsers, Edge before Chrome. Only existing paths."""
    found: list[Browser] = []
    for name, relative in ((EDGE, "Microsoft/Edge/Application/msedge.exe"),
                           (CHROME, "Google/Chrome/Application/chrome.exe")):
        for root in _program_files():
            if not root:
                continue
            path = Path(root) / relative
            if path.exists() and all(b.path != path for b in found):
                found.append(Browser(name=name, path=path))
    return found


def profile_dir() -> Path:
    """The dedicated, persistent automation profile."""
    path = user_data_dir() / PROFILE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return user_data_dir() / _STATE_FILE


def remembered() -> str | None:
    """Name of the browser that worked last time, if any."""
    path = _state_path()
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("browser")
    except (OSError, json.JSONDecodeError):
        return None


def remember(name: str) -> None:
    """Record which browser answered, so the next run tries it first."""
    try:
        with open(_state_path(), "w", encoding="utf-8") as handle:
            json.dump({"browser": name}, handle)
    except OSError:
        pass  # remembering is an optimisation, never a hard failure


def ordered_candidates() -> list[Browser]:
    """Installed browsers with the remembered one moved to the front."""
    found = candidates()
    preferred = remembered()
    if not preferred:
        return found
    return sorted(found, key=lambda b: b.name != preferred)


def endpoint_browser(port: int = DEFAULT_PORT) -> str | None:
    """
    The browser already listening on ``port``, or ``None``.

    Reads ``/json/version``; the ``Browser`` field looks like ``Edg/141.0`` or
    ``Chrome/141.0``.
    """
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=2
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None
    label = str(payload.get("Browser", "")).lower()
    if "edg" in label:
        return EDGE
    if "chrome" in label or "chromium" in label:
        return CHROME
    return label or "desconhecido"


def _wait_for_endpoint(port: int, deadline: float) -> str | None:
    while time.monotonic() < deadline:
        name = endpoint_browser(port)
        if name:
            return name
        time.sleep(_POLL_SECONDS)
    return None


def launch(port: int = DEFAULT_PORT) -> str:
    """
    Make sure a debuggable browser is listening on ``port``; return its name.

    Reuses an already-running one (so we never fight a session the user is
    logged into), otherwise tries each installed browser in turn.
    """
    running = endpoint_browser(port)
    if running:
        remember(running)
        return running

    installed = ordered_candidates()
    if not installed:
        raise BrowserNotFound(
            "Nenhum navegador suportado encontrado. Instale o Microsoft Edge "
            "ou o Google Chrome."
        )

    failures: list[str] = []
    for browser in installed:
        try:
            subprocess.Popen(
                [
                    str(browser.path),
                    f"--remote-debugging-port={port}",
                    f"--user-data-dir={profile_dir()}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    # Keep the page running when its window is minimised or
                    # covered. Chromium reports document.visibilityState
                    # "hidden" then and freezes CSS transitions -- and the
                    # site's Bootstrap modals never finish opening or closing,
                    # so "Fechar" looks broken (measured 2026-09-09).
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-background-timer-throttling",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            failures.append(f"{browser.name}: {error}")
            continue

        name = _wait_for_endpoint(port, time.monotonic() + _STARTUP_TIMEOUT_SECONDS)
        if name:
            remember(name)
            return name
        failures.append(f"{browser.name}: nao respondeu na porta {port}")

    raise BrowserNotFound(
        "Nenhum navegador subiu com depuracao remota. Tentativas: "
        + "; ".join(failures)
    )
