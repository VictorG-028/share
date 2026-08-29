"""
The only file in ``modules/tui`` that imports ``prompt_toolkit``. Wires the
pure ``FormState``/``render_text`` to a real key-driven ``Application``.

A single self-managed ``Window``/``FormattedTextControl`` is used instead of
composing multiple ``prompt_toolkit`` input widgets -- the grid's focus
concept is entirely owned by ``FormState.row``/``field``, not
``prompt_toolkit``'s own widget focus chain, which doesn't fit a custom
cross-field grid anyway.
"""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

from modules.tui.render import render_text
from modules.tui.state import FormState


def build_application(state: FormState, *, input=None, output=None) -> Application:
    control = FormattedTextControl(lambda: ANSI(render_text(state)))
    layout = Layout(Window(content=control))
    bindings = KeyBindings()

    @bindings.add("left")
    def _left(event):
        state.move_left()
        event.app.invalidate()

    @bindings.add("right")
    def _right(event):
        state.move_right()
        event.app.invalidate()

    @bindings.add("up")
    @bindings.add("w")
    def _up(event):
        state.bump_value(+1)
        event.app.invalidate()

    @bindings.add("down")
    @bindings.add("s")
    def _down(event):
        state.bump_value(-1)
        event.app.invalidate()

    @bindings.add("enter")
    def _enter(event):
        result = state.try_submit()
        if result is not None:
            event.app.exit(result=result)
        # else: blocked -- the status line already shows why, stay on the form.

    @bindings.add("escape")
    @bindings.add("c-c")
    def _cancel(event):
        event.app.exit(result=None)

    return Application(
        layout=layout,
        key_bindings=bindings,
        full_screen=True,
        input=input,
        output=output,
    )


def run_tui() -> list[str] | None:
    state = FormState.initial()
    return build_application(state).run()
