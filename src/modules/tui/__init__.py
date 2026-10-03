"""
The interactive screens that replace typing flags by hand: a start menu, the
appointment form and the refresh form.

The ``*_state``/``argv_builder``/``*render``/``keys_legend`` modules are pure --
no ``prompt_toolkit`` import, plain-pytest testable. ``app.py`` is the only
file that imports ``prompt_toolkit``; it's tested with
``create_pipe_input()``/``DummyOutput`` instead of a real terminal.
"""

from __future__ import annotations

from modules.tui.app import run_menu, run_refresh_tui, run_tui

__all__ = ["run_menu", "run_refresh_tui", "run_tui"]
