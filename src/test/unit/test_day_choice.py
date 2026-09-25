"""
Which day's OSI list gets read -- the rule, without a browser.

The headings below are verbatim from the live screen on 2026-09-10, including
the holiday (07/09, Independencia) that the site writes as ``FERIADO`` where
every other day carries a weekday name. That substitution is the only signal
there is for a company holiday, so it is worth pinning.
"""

from datetime import date

from modules.osi_catalog.day_choice import eligible_days, parse_panels

#: One filtered fortnight, exactly as the site rendered it.
PANELS = [
    {"stamp": "04/09/2026", "heading": "Sem registro 04/09/2026 SEXTA-FEIRA Sobre Aviso", "appointments": 1},
    {"stamp": "05/09/2026", "heading": "Sem registro 05/09/2026 SÁBADO Sobre Aviso", "appointments": 0},
    {"stamp": "06/09/2026", "heading": "Sem registro 06/09/2026 DOMINGO Sobre Aviso", "appointments": 0},
    {"stamp": "07/09/2026", "heading": "Sem registro 07/09/2026 FERIADO Sobre Aviso", "appointments": 0},
    {"stamp": "08/09/2026", "heading": "Sem registro 08/09/2026 TERÇA-FEIRA Sobre Aviso", "appointments": 1},
    {"stamp": "10/09/2026", "heading": "Sem registro 10/09/2026 QUINTA-FEIRA Sobre Aviso", "appointments": 0},
]


def test_parse_panels_reads_the_word_after_the_date():
    panels = parse_panels(PANELS)
    assert [p.word for p in panels] == [
        "SEXTA-FEIRA",
        "SÁBADO",
        "DOMINGO",
        "FERIADO",
        "TERÇA-FEIRA",
        "QUINTA-FEIRA",
    ]
    assert panels[0].day == date(2026, 9, 4)


def test_parse_panels_sorts_oldest_first_whatever_the_dom_order():
    panels = parse_panels(list(reversed(PANELS)))
    assert [p.day for p in panels] == sorted(p.day for p in panels)


def test_parse_panels_drops_a_panel_it_cannot_read():
    # Skipping a candidate costs one step down the ladder; guessing its word
    # could pick a day the site refuses to populate.
    assert parse_panels([{"stamp": "nao e data", "heading": "x"}]) == []
    assert parse_panels([{"stamp": "10/09/2026", "heading": "sem palavra depois"}]) == []


def test_holiday_and_weekend_are_recognised():
    by_day = {p.day: p for p in parse_panels(PANELS)}
    assert by_day[date(2026, 9, 7)].is_holiday
    assert by_day[date(2026, 9, 5)].is_weekend
    assert by_day[date(2026, 9, 6)].is_weekend
    assert not by_day[date(2026, 9, 10)].is_holiday
    assert not by_day[date(2026, 9, 10)].is_weekend


def test_eligible_days_is_newest_first_and_skips_the_unusable():
    # Today (10/09) leads: the newest day gives the freshest menu, and reading
    # a list creates nothing -- punching today stays forbidden elsewhere.
    assert eligible_days(parse_panels(PANELS)) == [
        date(2026, 9, 10),
        date(2026, 9, 8),
        date(2026, 9, 4),
    ]


def test_each_toggle_admits_only_its_own_kind_of_day():
    panels = parse_panels(PANELS)
    with_holiday = eligible_days(panels, include_holidays=True)
    assert date(2026, 9, 7) in with_holiday
    assert date(2026, 9, 5) not in with_holiday

    with_weekend = eligible_days(panels, include_weekends=True)
    assert {date(2026, 9, 5), date(2026, 9, 6)} <= set(with_weekend)
    assert date(2026, 9, 7) not in with_weekend


def test_both_toggles_keep_every_day_on_screen():
    panels = parse_panels(PANELS)
    assert eligible_days(panels, include_holidays=True, include_weekends=True) == sorted(
        (p.day for p in panels), reverse=True
    )


def test_a_fortnight_of_nothing_but_holidays_has_no_candidate():
    # The caller turns this into "use --incluir-feriado", which is the only
    # honest answer: there is no workday to read a list from.
    only_holidays = parse_panels(
        [{"stamp": "07/09/2026", "heading": "Sem registro 07/09/2026 FERIADO x", "appointments": 0}]
    )
    assert eligible_days(only_holidays) == []
