from datetime import date

from core import cache
from services import report_repository

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
    cache.set_json(cache_key, _CACHE_EMPTY if data is None else data, cache.ttl_seconds(ttl_date))
    return data


def list_team_reports(limit: int) -> list[dict]:
    cache_key = f"report:team:list:{limit}"
    return _load_cached_report(
        cache_key,
        date.today(),
        lambda: report_repository.list_reports(TEAM_REPORT_TABLE, limit=limit),
    )


def get_team_report(report_date: date) -> dict | None:
    cache_key = f"report:team:{report_date.isoformat()}"
    return _load_cached_report(
        cache_key,
        report_date,
        lambda: report_repository.get_report(TEAM_REPORT_TABLE, report_date),
    )


def list_player_reports(player_id: int, limit: int) -> list[dict]:
    cache_key = f"report:player:{player_id}:list:{limit}"
    return _load_cached_report(
        cache_key,
        date.today(),
        lambda: report_repository.list_reports(
            PLAYER_REPORT_TABLE,
            limit=limit,
            player_id=player_id,
        ),
    )


def get_player_report(player_id: int, report_date: date) -> dict | None:
    cache_key = f"report:player:{player_id}:{report_date.isoformat()}"
    return _load_cached_report(
        cache_key,
        report_date,
        lambda: report_repository.get_report(
            PLAYER_REPORT_TABLE,
            report_date,
            player_id=player_id,
        ),
    )
