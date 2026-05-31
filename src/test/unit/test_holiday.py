"""Holiday module -- exercised offline (allow_network=False) to avoid the API."""

from datetime import date

from modules.holiday.service import (
    FIXED_NATIONAL,
    _fallback,
    get_holidays,
    is_holiday,
)

YEAR = 2026


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
