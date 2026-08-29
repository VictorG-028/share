import pytest

from modules.osi_catalog import cache
from modules.osi_catalog.entry import OsiEntry


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
