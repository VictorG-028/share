"""
The only file in ``modules/tui`` that imports ``prompt_toolkit``. Wires the
pure states/renderers to real key-driven ``Application`` objects.

A single self-managed ``Window``/``FormattedTextControl`` is used per screen
instead of composing multiple ``prompt_toolkit`` input widgets -- the focus
concept is entirely owned by each state's ``focus``, not ``prompt_toolkit``'s
own widget focus chain, which doesn't fit a custom form anyway.

All three screens (menu, appointment form, refresh form) share **one** key map,
:func:`_key_bindings`, so a key can never mean one thing here and another
there -- that inconsistency is what made the old form hard to use:

* Up/Down (and Shift-Tab/Tab) change the *line*, never a value;
* Left/Right change the focused value;
* Enter/Space go forward -- ``state.activate()`` decides what that means
  (change a value, open the OSI list, open a menu item, or execute);
* Esc/Backspace/Ctrl-C cancel and close.

The OSI overlay is not a second ``Application``: it is a mode of the same
state (``FormState.osi.picking``), so the same keys apply and Esc/Backspace
close the list instead of the form.
"""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

from modules.tui.menu_render import render_menu
from modules.tui.menu_state import MenuState
from modules.tui.refresh_render import render_refresh
from modules.tui.refresh_state import RefreshFormState
from modules.tui.render import render_text
from modules.tui.state import FormState


def _key_bindings(state, *, close_overlay=None) -> KeyBindings:
    """
    The shared key map. ``state`` needs ``move_next``/``move_prev``/``activate``
    and, optionally, ``bump_value`` (the menu has no value to change).

    ``activate`` returns the screen's result when the press finishes it and
    ``None`` to stay. ``close_overlay`` is asked first by Esc/Backspace and
    returns ``True`` when it closed something (the OSI list) -- in which case
    the form itself stays open.
    """
    bindings = KeyBindings()
    bump = getattr(state, "bump_value", None)

    @bindings.add("up")
    @bindings.add("s-tab")
    def _prev(event):
        state.move_prev()
        event.app.invalidate()

    @bindings.add("down")
    @bindings.add("tab")
    def _next(event):
        state.move_next()
        event.app.invalidate()

    @bindings.add("left")
    def _left(event):
        if bump is not None:
            bump(-1)
        event.app.invalidate()

    @bindings.add("right")
    def _right(event):
        if bump is not None:
            bump(+1)
        event.app.invalidate()

    @bindings.add("enter")
    @bindings.add(" ")
    def _forward(event):
        result = state.activate()
        if result is not None:
            event.app.exit(result=result)
        # else: a value moved, a list opened/closed, or the button was pressed
        # on a blocked form -- the screen already says which.
        event.app.invalidate()

    # eager: act on Esc as soon as the parser knows it is a lone Esc, instead of
    # also waiting ``timeoutlen`` for a meta-key combination nobody here uses.
    @bindings.add("escape", eager=True)
    @bindings.add("backspace")
    def _back(event):
        if close_overlay is not None and close_overlay():
            event.app.invalidate()
            return
        event.app.exit(result=None)

    @bindings.add("c-c")
    def _abort(event):
        # Always leaves, overlay or not: Ctrl-C is "get me out", and having to
        # press it twice would be a trap, not a safeguard.
        event.app.exit(result=None)

    return bindings


#: How long a lone Esc waits to learn it is not the start of an arrow key's
#: escape sequence. ``prompt_toolkit`` defaults to 0.5 s -- measured on a real
#: ConPTY (2026-10-03), cancelling with Esc took 560 ms. 50 ms is far above the
#: gap inside one sequence on a local console and below what a hand can feel.
ESC_TIMEOUT = 0.05


def _application(render, state, bindings, *, input=None, output=None) -> Application:
    control = FormattedTextControl(lambda: ANSI(render(state)))
    app = Application(
        layout=Layout(Window(content=control)),
        key_bindings=bindings,
        full_screen=True,
        input=input,
        output=output,
        # Redraw at once. The default (0.01) makes the scheduler re-queue itself
        # until 10 ms have passed before drawing -- a fixed floor under every
        # keypress (measured: 12 ms to the first byte, now ~2 ms) for no gain on
        # a screen this small, where there is no CPU load to be fair to.
        max_render_postpone_time=None,
    )
    app.ttimeoutlen = ESC_TIMEOUT
    return app


# --------------------------------------------------------------------- form


def build_application(state: FormState, *, input=None, output=None) -> Application:
    def close_picker() -> bool:
        if state.osi.picking:
            state.osi.cancel_pick()
            return True
        return False

    bindings = _key_bindings(state, close_overlay=close_picker)
    return _application(render_text, state, bindings, input=input, output=output)


def run_tui() -> list[str] | None:
    state = FormState.initial()
    return build_application(state).run()


# ------------------------------------------------------------------ refresh


def build_refresh_application(
    state: RefreshFormState, *, input=None, output=None
) -> Application:
    """
    The "Atualizar lista de OSI" screen: a source spinner, two toggles and the
    button.

    A separate ``Application`` from the form -- the two screens answer
    different questions and share no field -- but built from the same key map
    and living here so this file stays the only one that imports
    ``prompt_toolkit``.
    """
    return _application(render_refresh, state, _key_bindings(state), input=input, output=output)


def run_refresh_tui() -> list[str] | None:
    """The chosen options as argv, or ``None`` when cancelled.

    An empty list means "all defaults" and is a real answer -- callers must
    compare against ``None``, never test truthiness.
    """
    state = RefreshFormState.initial()
    return build_refresh_application(state).run()


# --------------------------------------------------------------------- menu


def build_menu_application(state: MenuState, *, input=None, output=None) -> Application:
    return _application(render_menu, state, _key_bindings(state), input=input, output=output)


def run_menu() -> str | None:
    """The key of the chosen operation (see ``menu_state``), or ``None`` when closed."""
    return build_menu_application(MenuState()).run()
