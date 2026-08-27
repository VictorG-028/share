"""
User-writable paths.

A frozen build (PyInstaller onefile) unpacks its bundle into a temporary
directory that is recreated on every run, so ``Path(__file__).parent`` is fine
for READING packaged data and useless for WRITING anything that must survive.
Everything the app writes -- caches, remembered state, the browser profile --
goes under :func:`user_data_dir` instead.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "auto-appointment"


def is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) bundle."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """
    Root for READ-ONLY packaged data.

    Frozen: the temporary extraction dir (``sys._MEIPASS``). Otherwise: ``src``.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    """Per-user directory for everything the app writes. Created on demand."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
