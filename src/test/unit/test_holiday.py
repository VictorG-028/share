"""Holiday module -- exercised offline (allow_network=False) to avoid the API."""

import urllib.error
from datetime import date

import pytest

from modules.holiday import service
from modules.holiday.service import (
    FIXED_NATIONAL,
    _fallback,
    get_holidays,
    is_holiday,
)

YEAR = 2026


@pytest.fixture(autouse=True)
def _fresh_process_state():
    """The memory is per process; every test starts as if the process were new."""
    service._memo.clear()
    service._network_failed.clear()
    yield
    service._memo.clear()
    service._network_failed.clear()


def test_fallback_contains_fixed_national_holidays():
    days = _fallback(YEAR)
    assert date(YEAR, 9, 7) in days          # Independência
    assert date(YEAR, 12, 25) in days         # Natal
    assert len(days) == len(FIXED_NATIONAL)


def test_is_holiday_true_for_fixed_holiday_offline():
    # 7 Sep is a fixed national holiday -> present in both fallback and any cache.
    assert is_holiday(date(YEAR, 9, 7), allow_network=False) is True


def test_is_holiday_false_for_ordinary_day_offline():
    # 17 Mar is never a national holiday (and not a fixed one).
    assert is_holiday(date(YEAR, 3, 17), allow_network=False) is False


def test_get_holidays_offline_returns_at_least_fallback():
    days = get_holidays(YEAR, allow_network=False)
    # Whether served from cache or fallback, the fixed holidays are present.
    assert _fallback(YEAR).issubset(days)


# ---------------------------------------------- speed: what the form leans on
# The form asks about the same year on every date change. These pin the three
# things that made that slow: a request BrasilAPI refused, a network retried
# on every keypress, and a JSON file re-read on every call.


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_data_dir", lambda: tmp_path / "holidays")
    return tmp_path / "holidays"


def test_the_request_carries_a_user_agent_of_its_own(monkeypatch):
    # urllib's default ``Python-urllib/3.x`` gets a 403 from BrasilAPI.
    seen = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, *_a):
            return b'[{"date": "2026-09-07"}]'

    def _urlopen(request, timeout=None):
        seen["agent"] = request.get_header("User-agent")
        return _Response()

    monkeypatch.setattr(service.urllib.request, "urlopen", _urlopen)
    assert service._fetch_from_api(2026) == {date(2026, 9, 7)}
    assert seen["agent"] == service._USER_AGENT
    assert not seen["agent"].startswith("Python-urllib")


def test_a_failing_network_is_tried_once_per_year_not_once_per_call(isolated_cache, monkeypatch):
    calls = []

    def _boom(year):
        calls.append(year)
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)

    monkeypatch.setattr(service, "_fetch_from_api", _boom)
    for _ in range(5):
        assert is_holiday(date(YEAR, 9, 7)) is True  # still answered, by the fallback
    assert calls == [YEAR]
    get_holidays(YEAR + 1)
    assert calls == [YEAR, YEAR + 1]  # another year is its own attempt


def test_an_offline_call_does_not_count_as_a_failed_attempt(isolated_cache, monkeypatch):
    calls = []
    monkeypatch.setattr(
        service, "_fetch_from_api", lambda year: calls.append(year) or {date(year, 1, 1)}
    )
    get_holidays(YEAR, allow_network=False)  # never touched the network
    assert calls == []
    assert get_holidays(YEAR) == {date(YEAR, 1, 1)}  # so it still gets to try
    assert calls == [YEAR]


def test_a_year_that_answered_is_cached_on_disk_and_kept_in_memory(isolated_cache, monkeypatch):
    fetches, reads = [], []
    monkeypatch.setattr(
        service, "_fetch_from_api", lambda year: fetches.append(year) or {date(year, 4, 21)}
    )
    real_read = service._read_cache
    monkeypatch.setattr(service, "_read_cache", lambda year: reads.append(year) or real_read(year))

    assert is_holiday(date(YEAR, 4, 21)) is True
    assert (isolated_cache / f"holidays_{YEAR}.json").exists()  # written for the next run
    for _ in range(5):
        assert is_holiday(date(YEAR, 4, 21)) is True
    assert fetches == [YEAR]
    assert reads == [YEAR]  # the file was read once, not on every call


def test_the_cache_on_disk_serves_a_new_process_without_the_network(isolated_cache, monkeypatch):
    isolated_cache.mkdir(parents=True)
    (isolated_cache / f"holidays_{YEAR}.json").write_text('["2026-02-17"]', encoding="utf-8")

    def _boom(year):
        raise AssertionError("o cache em disco deveria bastar")

    monkeypatch.setattr(service, "_fetch_from_api", _boom)
    assert is_holiday(date(YEAR, 2, 17)) is True


def test_refresh_replaces_what_the_memory_holds(isolated_cache, monkeypatch):
    monkeypatch.setattr(service, "_fetch_from_api", lambda year: {date(year, 1, 1)})
    assert get_holidays(YEAR) == {date(YEAR, 1, 1)}
    monkeypatch.setattr(service, "_fetch_from_api", lambda year: {date(year, 2, 2)})
    assert service.refresh(YEAR) == {date(YEAR, 2, 2)}
    assert get_holidays(YEAR) == {date(YEAR, 2, 2)}
