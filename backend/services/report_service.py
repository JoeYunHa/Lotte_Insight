from datetime import date

from core import cache
from core.time_utils import today_kst
from services import report_repository
from services.cache_keys import CacheKeyBuilder

TEAM_REPORT_TABLE = "team_daily_report"
PLAYER_REPORT_TABLE = "player_daily_report"


_CACHE_EMPTY = "__empty__"


def _load_cached_report(
    cache_key: str,
    ttl_date: date,
    loader,
):
    raw = cache.get_json(cache_key)
    if raw is not None:
        return None if raw == _CACHE_EMPTY else raw

    data = loader()
    today = today_kst()
    if data is None and ttl_date >= today:
        return None
    cache.set_json(cache_key, _CACHE_EMPTY if data is None else data, cache.ttl_seconds(ttl_date))
    return data


def list_team_reports(limit: int) -> list[dict]:
    cache_key = CacheKeyBuilder.team_report_list(limit=limit)
    return _load_cached_report(
        cache_key,
        today_kst(),
        lambda: report_repository.list_reports(TEAM_REPORT_TABLE, limit=limit),
    ) or []


def get_team_report(report_date: date) -> dict | None:
    cache_key = CacheKeyBuilder.team_report(report_date=report_date)
    return _load_cached_report(
        cache_key,
        report_date,
        lambda: report_repository.get_report(TEAM_REPORT_TABLE, report_date),
    )


def list_player_reports(player_id: int, limit: int) -> list[dict]:
    cache_key = CacheKeyBuilder.player_report_list(player_id=player_id, limit=limit)
    return _load_cached_report(
        cache_key,
        today_kst(),
        lambda: report_repository.list_reports(
            PLAYER_REPORT_TABLE,
            limit=limit,
            player_id=player_id,
        ),
    ) or []


def get_player_report(player_id: int, report_date: date) -> dict | None:
    cache_key = CacheKeyBuilder.player_report(player_id=player_id, report_date=report_date)
    return _load_cached_report(
        cache_key,
        report_date,
        lambda: report_repository.get_report(
            PLAYER_REPORT_TABLE,
            report_date,
            player_id=player_id,
        ),
    )
