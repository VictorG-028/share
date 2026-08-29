"""
The interactive grid-form that replaces typing flags by hand.

``state.py``/``argv_builder.py``/``render.py`` are pure -- no ``prompt_toolkit``
import, plain-pytest testable. ``app.py`` is the only file that imports
``prompt_toolkit``; it's tested with ``create_pipe_input()``/``DummyOutput``
instead of a real terminal.
"""

from __future__ import annotations

from modules.tui.app import run_tui

__all__ = ["run_tui"]
