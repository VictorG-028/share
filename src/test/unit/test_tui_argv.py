from datetime import date

from modules.osi_catalog.entry import OsiEntry
from modules.tui.argv_builder import build_argv
from modules.tui.state import DateCursor, FormState, OsiSpinner

DAY = date(2026, 5, 29)


def _state(*, force: bool = False, save: bool = True) -> FormState:
    return FormState(
        date=DateCursor(day=DAY.day, month=DAY.month, year=DAY.year, force=force),
        osi=OsiSpinner(entries=[OsiEntry(number="82695", label="OSI 82695")]),
        save=save,
    )


def test_save_yes_produces_save_and_yes_flags():
    argv = build_argv(_state(save=True))
    assert argv == ["--day", "29/05/2026", "--osi", "OSI 82695", "--save", "--yes"]


def test_save_no_produces_fill_only():
    argv = build_argv(_state(save=False))
    assert argv == ["--day", "29/05/2026", "--osi", "OSI 82695", "--fill"]


def test_force_on_adds_the_flag():
    argv = build_argv(_state(force=True, save=True))
    assert "--force" in argv


def test_force_off_omits_the_flag():
    argv = build_argv(_state(force=False, save=True))
    assert "--force" not in argv


def test_an_unnumbered_osi_travels_as_its_whole_label():
    # The manager's OSIs have no number to send; the label is the identity.
    label = "coe tech - setembro - 2026 | Walber Hugo da Silva - 427465"
    state = _state()
    state.osi = OsiSpinner(entries=[OsiEntry.from_label(label)])
    assert build_argv(state)[2:4] == ["--osi", label]


def test_no_osi_at_all_sends_no_flag():
    state = _state()
    state.osi = OsiSpinner(entries=[])
    assert "--osi" not in build_argv(state)
