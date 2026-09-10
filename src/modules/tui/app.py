"""
The only file in ``modules/tui`` that imports ``prompt_toolkit``. Wires the
pure ``FormState``/``render_text`` to a real key-driven ``Application``.

A single self-managed ``Window``/``FormattedTextControl`` is used instead of
composing multiple ``prompt_toolkit`` input widgets -- the grid's focus
concept is entirely owned by ``FormState.row``/``field``, not
``prompt_toolkit``'s own widget focus chain, which doesn't fit a custom
cross-field grid anyway.

The OSI overlay is not a second ``Application`` either: it is a mode of the
same state (``FormState.osi.picking``), so every key below asks that first
and the renderer draws whichever screen is current.
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

    def on_osi() -> bool:
        return state.focus_name() == "osi"

    @bindings.add("left")
    def _left(event):
        if not state.osi.picking:
            state.move_left()
        event.app.invalidate()

    @bindings.add("right")
    def _right(event):
        if not state.osi.picking:
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

    @bindings.add("tab")
    def _tab(event):
        # Opens the list, and inside it goes back without changing anything.
        if state.osi.picking:
            state.osi.cancel_pick()
        elif on_osi():
            state.osi.open_picker()
        event.app.invalidate()

    @bindings.add(" ")
    def _space(event):
        if state.osi.picking:
            state.osi.choose()
        elif on_osi():
            state.osi.open_picker()
        event.app.invalidate()

    @bindings.add("enter")
    def _enter(event):
        if state.osi.picking:
            state.osi.choose()
            event.app.invalidate()
            return
        if on_osi():
            # On the OSI row, Enter opens the list instead of submitting --
            # you are standing on the field whose value it picks.
            state.osi.open_picker()
            event.app.invalidate()
            return
        result = state.try_submit()
        if result is not None:
            event.app.exit(result=result)
        # else: blocked -- the status line already shows why, stay on the form.

    @bindings.add("escape")
    def _escape(event):
        if state.osi.picking:
            state.osi.cancel_pick()
            event.app.invalidate()
            return
        event.app.exit(result=None)

    @bindings.add("c-c")
    def _abort(event):
        # Always leaves, overlay or not: Ctrl-C is "get me out", and having to
        # press it twice would be a trap, not a safeguard.
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
