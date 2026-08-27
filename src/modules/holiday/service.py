from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from modules.paths import user_data_dir

# Brazilian national holidays. Source order: local cache -> BrasilAPI -> offline
# fallback. BrasilAPI is free and key-less; we use stdlib urllib so no extra
# dependency is added.
API_URL = "https://brasilapi.com.br/api/feriados/v1/{year}"
_TIMEOUT_SECONDS = 5

def _data_dir() -> Path:
    """
    Where the per-year cache lives: under the user's data dir, never next to
    the module. A frozen build unpacks itself into a temporary directory that
    is recreated on every run, so a cache written there would vanish.
    """
    return user_data_dir() / "holidays"

# Offline fallback: FIXED-DATE national holidays only, keyed by (month, day).
# Movable holidays (Carnaval, Sexta-feira Santa, Corpus Christi) are tied to
# Easter and are NOT here -- they are only covered when the API or a populated
# cache is available.
FIXED_NATIONAL: dict[tuple[int, int], str] = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Consciência Negra",
    (12, 25): "Natal",
}


def _cache_file(year: int) -> Path:
    return _data_dir() / f"holidays_{year}.json"


def _read_cache(year: int) -> set[date] | None:
    path = _cache_file(year)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return {date.fromisoformat(s) for s in json.load(handle)}
    except (OSError, ValueError):
        return None


def _write_cache(year: int, days: set[date]) -> None:
    _data_dir().mkdir(parents=True, exist_ok=True)
    with open(_cache_file(year), "w", encoding="utf-8") as handle:
        json.dump(sorted(d.isoformat() for d in days), handle, ensure_ascii=False, indent=2)


def _fetch_from_api(year: int) -> set[date]:
    url = API_URL.format(year=year)
    with urllib.request.urlopen(url, timeout=_TIMEOUT_SECONDS) as response:
        payload = json.load(response)
    return {date.fromisoformat(item["date"]) for item in payload}


def _fallback(year: int) -> set[date]:
    return {date(year, month, day) for (month, day) in FIXED_NATIONAL}


def get_holidays(year: int, *, allow_network: bool = True) -> set[date]:
    """
    Resolve the set of national holidays for ``year``.

    Tries the local cache first; then BrasilAPI (caching the result); finally the
    offline fixed-date fallback. Set ``allow_network=False`` to skip the API
    entirely (used by tests and offline runs).
    """
    cached = _read_cache(year)
    if cached is not None:
        return cached
    if allow_network:
        try:
            days = _fetch_from_api(year)
            _write_cache(year, days)
            return days
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            pass
    return _fallback(year)


def refresh(year: int) -> set[date]:
    """Force a re-fetch from BrasilAPI and overwrite the cache for ``year``."""
    days = _fetch_from_api(year)
    _write_cache(year, days)
    return days


def is_holiday(d: date, *, allow_network: bool = True) -> bool:
    """True if ``d`` is a Brazilian national holiday."""
    return d in get_holidays(d.year, allow_network=allow_network)
