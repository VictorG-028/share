"""The pure pieces of creating an OSI: no browser, no network."""

from datetime import date

import pytest

from modules.osi_register import (
    default_description,
    hours_for_eight_per_day,
    parse_hours,
    parse_window,
)


def test_parse_window_reads_the_sites_rejection_popup():
    text = "Atenção! O período informado deve estar entre 01/09/2026 à 30/09/2026."
    assert parse_window(text) == (date(2026, 9, 1), date(2026, 9, 30))


@pytest.mark.parametrize("joiner", ["a", "até"])
def test_parse_window_tolerates_other_joiners(joiner):
    assert parse_window(f"de 17/08/2026 {joiner} 15/09/2026.") == (date(2026, 8, 17), date(2026, 9, 15))


def test_parse_window_rejects_text_without_a_period():
    with pytest.raises(ValueError):
        parse_window("Perfeito! Registros alterados com sucesso")


def test_parse_window_rejects_an_inverted_period():
    with pytest.raises(ValueError):
        parse_window("30/09/2026 à 01/09/2026")


def test_default_description_names_the_start_month():
    assert default_description(date(2026, 9, 1)) == "Criando OSI do mes setembro"
    assert default_description(date(2026, 3, 31)) == "Criando OSI do mes março"


def test_parse_hours_accepts_the_brazilian_comma():
    assert parse_hours("5,00") == 5.0
    assert parse_hours("1.234,50") == 1234.5
    assert parse_hours("8") == 8.0


def test_parse_hours_rejects_garbage():
    with pytest.raises(ValueError):
        parse_hours("N/A")


def test_hours_for_eight_per_day_scales_the_probe():
    # 40h showed 2,67/day -> the site counted 15 business days -> 120h.
    assert hours_for_eight_per_day(40, 40 / 15) == 120
    # 40h over 5 business days already reads 8.
    assert hours_for_eight_per_day(40, 8.0) == 40


def test_hours_for_eight_per_day_rejects_a_zero_reading():
    with pytest.raises(ValueError):
        hours_for_eight_per_day(40, 0)
