import pytest

from modules.tui import keys_legend as k
from modules.tui.keys_legend import KEYS_WIDTH, legend

MODES = [k.VALUE, k.OSI, k.RUN, k.PICKER, k.MENU]


@pytest.mark.parametrize("mode", MODES)
def test_every_legend_is_plain_ascii(mode):
    # Arrows are spelled out: a glyph needs the console *font* to have it.
    assert legend(mode, run_effect="X").isascii()


@pytest.mark.parametrize("mode", MODES)
def test_every_key_is_written_as_a_bracketed_name(mode):
    for line in legend(mode, run_effect="X").splitlines():
        keys = line[2 : 2 + KEYS_WIDTH].strip()
        assert keys.startswith("[") and keys.endswith("]"), line
        for part in keys.split(" / "):
            assert part.startswith("[") and part.endswith("]"), line


@pytest.mark.parametrize("mode", MODES)
def test_the_effect_starts_in_the_same_column_on_every_line_of_every_mode(mode):
    # Two spaces of indent, the key column, three spaces, then the effect --
    # always the same, so the footer never jumps when the focus changes.
    start = 2 + KEYS_WIDTH + 3
    for line in legend(mode, run_effect="X").splitlines():
        assert line[start - 3 : start] == "   ", line
        assert line[start] != " ", line


def test_the_longest_footer_line_fits_an_80_column_console():
    from modules.tui.refresh_render import RUN_EFFECT
    from modules.tui.render import RUN_EFFECT_FILL, RUN_EFFECT_SAVE

    for effect in (RUN_EFFECT, RUN_EFFECT_FILL, RUN_EFFECT_SAVE):
        for line in legend(k.RUN, run_effect=effect).splitlines():
            assert len(line) <= 80, line


def test_effects_are_named_by_kind():
    assert "MUDA" in legend(k.VALUE)
    assert "ABRE" in legend(k.OSI)
    assert "EXECUTA: ler" in legend(k.RUN, run_effect="ler")
    assert "ESCOLHE" in legend(k.PICKER)


def test_every_screen_says_how_to_cancel():
    assert "[ESC] / [BACKSPACE] / [CTRL-C]" in legend(k.VALUE)
    assert "[ESC] / [BACKSPACE] / [CTRL-C]" in legend(k.OSI)
    assert "[ESC] / [BACKSPACE] / [CTRL-C]" in legend(k.RUN, run_effect="X")
    assert "[ESC] / [BACKSPACE] / [CTRL-C]" in legend(k.MENU)


def test_the_picker_separates_going_back_from_closing_everything():
    text = legend(k.PICKER)
    assert "[ESC] / [BACKSPACE]   " in text and "voltar sem mudar" in text
    assert "[CTRL-C]" in text and "cancelar e fechar tudo" in text


def test_an_unknown_mode_is_an_error_not_an_empty_footer():
    with pytest.raises(ValueError):
        legend("nope")
