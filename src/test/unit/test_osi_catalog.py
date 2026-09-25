from datetime import date

import pytest

from modules.osi_catalog import cache
from modules.osi_catalog.entry import (
    NUMBER_NOT_CAPTURED,
    SOURCE_LISTING,
    SOURCE_TIMESHEET,
    OsiEntry,
)


@pytest.fixture
def files(tmp_path, monkeypatch):
    catalog = tmp_path / "osi_catalog.json"
    last_used = tmp_path / "osi_last_used.json"
    monkeypatch.setattr(cache, "catalog_file", lambda: catalog)
    monkeypatch.setattr(cache, "last_used_file", lambda: last_used)
    return catalog, last_used


def test_load_catalog_missing_file_is_empty(files):
    assert cache.load_catalog() == []


def test_load_catalog_corrupt_file_is_empty(files):
    catalog, _ = files
    catalog.write_text("not json", encoding="utf-8")
    assert cache.load_catalog() == []


def test_save_then_load_catalog_round_trips(files):
    entries = [
        OsiEntry(number="82695", label="OSI 82695 | Faturamento Assistencial SECONCI | Carga base historica - 417293"),
        OsiEntry(number="11111", label="OSI 11111 | Outro Projeto | Outra Atividade - 1"),
    ]
    cache.save_catalog(entries)
    assert cache.load_catalog() == entries


def test_load_last_used_missing_file_is_none(files):
    assert cache.load_last_used() is None


def test_load_last_used_corrupt_file_is_none(files):
    _, last_used = files
    last_used.write_text("not json", encoding="utf-8")
    assert cache.load_last_used() is None


def test_save_then_load_last_used_round_trips(files):
    cache.save_last_used("82695")
    assert cache.load_last_used() == "82695"


def test_from_label_takes_the_number_from_the_composite():
    label = "OSI 82695 | Faturamento Assistencial SECONCI | Carga base historica - 417293"
    assert OsiEntry.from_label(label) == OsiEntry(number="82695", label=label)


def test_from_label_strips_surrounding_whitespace():
    assert OsiEntry.from_label("  OSI 11111 | P | A - 1\n").number == "11111"


def test_from_label_keeps_a_label_that_has_no_number():
    # What the manager opens for the whole team: no "OSI <n>" prefix at all.
    # It is listed for the day, so it is punchable, so it must be captured.
    label = "coe tech - setembro - 2026 | Walber Hugo da Silva - 427465"
    assert OsiEntry.from_label(label) == OsiEntry(
        number=NUMBER_NOT_CAPTURED, label=label
    )


def test_from_label_never_rejects_anything():
    assert OsiEntry.from_label("Aberto").number == NUMBER_NOT_CAPTURED
    assert OsiEntry.from_label("Aberto").label == "Aberto"


def test_last_used_reads_the_number_written_by_an_older_build(files):
    # Still a usable selector: a bare number matches exactly its own row.
    _, last_used = files
    last_used.write_text('{"osi_number": "82695"}', encoding="utf-8")
    assert cache.load_last_used() == "82695"


def test_load_catalog_survives_an_entry_without_a_number(files):
    catalog, _ = files
    catalog.write_text('{"entries": [{"label": "coe tech | Fulano - 1"}]}', encoding="utf-8")
    assert cache.load_catalog() == [
        OsiEntry(number=NUMBER_NOT_CAPTURED, label="coe tech | Fulano - 1")
    ]


# --------------------------------------------------- the listing as a source


#: One object from ``osi/get-by-parameters``, trimmed to the fields that matter.
#: Read from the live endpoint on 2026-09-10; the label built out of it matched
#: the row the timesheet's "?" listed, character for character.
RECORD = {
    "Id": "83385",
    "ProjectName": "Faturamento Assistencial SECONCI",
    "ActivityName": "Homologacao End2End - Suporte",
    "ActivityId": "417294",
    "StatusName": "Liberado",
    "OsiActivityStartDateStr": "08/09/2026",
    "OsiActivityEndDateStr": "11/09/2026",
}


def test_from_record_rebuilds_the_label_the_site_shows():
    entry = OsiEntry.from_record(RECORD)
    assert entry.label == (
        "OSI 83385 | Faturamento Assistencial SECONCI | Homologacao End2End - Suporte - 417294"
    )
    assert entry.number == "83385"
    assert entry.status == "Liberado"
    assert (entry.start, entry.end) == (date(2026, 9, 8), date(2026, 9, 11))
    assert entry.source == SOURCE_LISTING


def test_from_record_without_an_activity_id_stops_before_the_dash():
    # The fallback that reads the screen's table has no activity id to give.
    entry = OsiEntry.from_record({**RECORD, "ActivityId": ""})
    assert entry.label.endswith("Homologacao End2End - Suporte")


def test_liberado_outside_its_window_is_not_punchable():
    # The real 82695: Liberado forever, window closed on 30/08, and the site
    # simply stopped listing it.
    entry = OsiEntry.from_record(
        {**RECORD, "Id": "82695", "OsiActivityStartDateStr": "17/08/2026",
         "OsiActivityEndDateStr": "30/08/2026"}
    )
    assert entry.is_punchable(date(2026, 8, 20))
    assert not entry.is_punchable(date(2026, 9, 10))


def test_a_status_that_is_not_liberado_is_never_punchable():
    entry = OsiEntry.from_record({**RECORD, "StatusName": "Cancelado"})
    assert not entry.is_punchable(date(2026, 9, 10))


def test_an_entry_without_status_or_window_is_punchable():
    # Everything the day's "?" offers is punchable that day; silence from the
    # site is not a "no".
    assert OsiEntry.from_label("coe tech - setembro - 2026 | Fulano - 1").is_punchable(
        date(2026, 9, 10)
    )


def test_punchable_filters_a_mixed_catalog():
    entries = [
        OsiEntry.from_label("coe tech - setembro - 2026 | Fulano - 1"),
        OsiEntry.from_record(RECORD),
        OsiEntry.from_record({**RECORD, "Id": "1", "StatusName": "Finalizado"}),
    ]
    assert [e.number for e in cache.punchable(entries, date(2026, 9, 10))] == [
        NUMBER_NOT_CAPTURED,
        "83385",
    ]


# ------------------------------------------------------------------- merging


def test_a_source_only_overwrites_itself():
    existing = [
        OsiEntry.from_label("coe tech - setembro - 2026 | Fulano - 1"),
        OsiEntry.from_record({**RECORD, "Id": "999"}),
    ]
    fresh = [OsiEntry.from_label("OSI 83270 | P | A - 2")]
    merged = cache.merge_entries(existing, fresh, source=SOURCE_TIMESHEET)
    labels = [e.label for e in merged]
    # The timesheet capture replaced the timesheet entry and left the listing
    # one alone -- running the fast source daily must not lose the statuses.
    assert "OSI 83270 | P | A - 2" in labels
    assert "coe tech - setembro - 2026 | Fulano - 1" not in labels
    assert any(e.number == "999" for e in merged)


def test_the_same_osi_from_both_sources_becomes_one_entry():
    timesheet = [OsiEntry.from_label(
        "OSI 83385 | Faturamento Assistencial SECONCI | Homologacao End2End - Suporte - 417294"
    )]
    merged = cache.merge_entries(timesheet, [OsiEntry.from_record(RECORD)], source=SOURCE_LISTING)
    assert len(merged) == 1
    entry = merged[0]
    # Label from the list the site actually shows (it is what gets matched when
    # filling), status and window from the only source that knows them.
    assert entry.source == SOURCE_TIMESHEET
    assert entry.status == "Liberado"
    assert entry.end == date(2026, 9, 11)


def test_a_listing_only_osi_survives_the_merge():
    merged = cache.merge_entries([], [OsiEntry.from_record(RECORD)], source=SOURCE_LISTING)
    assert [e.number for e in merged] == ["83385"]


def test_save_and_load_round_trip_status_and_window(files):
    entries = [OsiEntry.from_record(RECORD)]
    cache.save_catalog(entries, sources={SOURCE_LISTING: {"count": 1}})
    assert cache.load_catalog() == entries
    assert cache.load_meta() == {SOURCE_LISTING: {"count": 1}}


def test_refreshing_the_timesheet_keeps_what_the_listing_knew():
    # Observed live on 2026-09-11: a plain --fonte apontamento turned 24 known
    # Liberado into 20, because the merged entry's source is the timesheet and
    # it was dropped together with the listing's status.
    both = cache.merge_entries(
        [OsiEntry.from_label(OsiEntry.from_record(RECORD).label)],
        [OsiEntry.from_record(RECORD)],
        source=SOURCE_LISTING,
    )
    assert both[0].status == "Liberado"

    again = cache.merge_entries(
        both,
        [OsiEntry.from_label(OsiEntry.from_record(RECORD).label)],
        source=SOURCE_TIMESHEET,
    )
    assert again[0].status == "Liberado"
    assert again[0].end == date(2026, 9, 11)


def test_a_listing_refresh_drops_a_status_it_no_longer_reports():
    # The listing defines every status; a number it stopped returning must not
    # keep the one it had, or a cancelled OSI would stay punchable forever.
    stale = cache.merge_entries(
        [OsiEntry.from_label(OsiEntry.from_record(RECORD).label)],
        [OsiEntry.from_record(RECORD)],
        source=SOURCE_LISTING,
    )
    refreshed = cache.merge_entries(stale, [], source=SOURCE_LISTING)
    assert refreshed[0].status is None
