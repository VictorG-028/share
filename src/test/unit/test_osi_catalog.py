import pytest

from modules.osi_catalog import cache
from modules.osi_catalog.entry import NUMBER_NOT_CAPTURED, OsiEntry


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
