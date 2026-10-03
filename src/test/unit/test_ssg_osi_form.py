"""Pure pieces of the OSI-form driver and its CLI: no browser, no network."""

import pytest

from modules.browser.ssg_list_modal import match_row as _match
from modules.osi_register.cli import build_parser

ROWS = [
    "47721 / COE-TECH-SETEMBRO-2025 / coe tech - setembro- 2025",
    "49179 / FASSECONCI / Faturamento Assistencial SECONCI",
    "50212 / COE-TECH-AGOSTO-2026 / coe tech - agosto - 2026",
]


def test_match_prefers_the_exact_row():
    assert _match(ROWS, ROWS[1]) == 1


def test_match_accepts_a_unique_substring_ignoring_case():
    assert _match(ROWS, "fasseconci") == 1
    assert _match(ROWS, "50212") == 2


ACCENTED_ROWS = [
    "OSI 83685 | Faturamento Assistencial SECONCI | Preparação Operação Assistida - 417487",
    "OSI 83686 | Faturamento Assistencial SECONCI | Homologação End2End - 417488",
]


def test_match_accepts_a_selector_typed_without_accents():
    assert _match(ACCENTED_ROWS, "preparacao operacao") == 0
    assert _match(ACCENTED_ROWS, "HOMOLOGACAO") == 1


def test_match_prefers_the_exact_accented_row():
    assert _match(ACCENTED_ROWS, ACCENTED_ROWS[1]) == 1


def test_match_refuses_an_ambiguity_found_only_without_accents():
    with pytest.raises(ValueError):
        _match(["Operação A", "Operação B"], "operacao")


def test_a_literal_hit_beats_the_accent_insensitive_one():
    # "operacao" is written exactly in the second row only, so that row wins.
    assert _match(["Operação A", "Operacao B"], "operacao") == 1


def test_match_refuses_an_ambiguous_substring():
    with pytest.raises(ValueError):
        _match(ROWS, "coe tech")


def test_match_refuses_an_unknown_label():
    with pytest.raises(ValueError):
        _match(ROWS, "nao existe")


def test_cli_defaults_are_interactive_and_dry():
    args = build_parser().parse_args([])
    assert not args.list and not args.yes
    assert args.project is None and args.activity is None and args.description is None


def test_cli_accepts_the_non_interactive_flags():
    args = build_parser().parse_args(["--project", "49179", "--activity", "carga", "--yes", "--port", "9223"])
    assert (args.project, args.activity, args.yes, args.port) == ("49179", "carga", True, 9223)
