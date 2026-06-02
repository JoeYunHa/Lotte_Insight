from datetime import date

from core.database import supabase
from core.time_utils import utc_day_bounds


def _fetch_article_player_rows(article_ids: list[int], select_clause: str) -> list[dict]:
    if not article_ids:
        return []
    result = (
        supabase.table("article_players")
        .select(select_clause)
        .in_("article_id", article_ids)
        .execute()
    )
    return result.data or []


def list_reports(
    table: str,
    *,
    limit: int,
    player_id: int | None = None,
) -> list[dict]:
    query = supabase.table(table).select("*")
    if player_id is not None:
        query = query.eq("player_id", player_id)
    result = query.order("date", desc=True).limit(limit).execute()
    return result.data or []


def get_report(
    table: str,
    report_date: date,
    *,
    player_id: int | None = None,
) -> dict | None:
    query = supabase.table(table).select("*").eq("date", report_date.isoformat())
    if player_id is not None:
        query = query.eq("player_id", player_id)
    result = query.maybe_single().execute()
    return result.data


def report_exists(
    table: str,
    report_date: date,
    *,
    player_id: int | None = None,
) -> bool:
    query = supabase.table(table).select("id").eq("date", report_date.isoformat())
    if player_id is not None:
        query = query.eq("player_id", player_id)
    return bool(query.maybe_single().execute().data)


import logging as _logging

_repo_logger = _logging.getLogger(__name__)


def save_report(table: str, row: dict, *, on_conflict: str) -> None:
    result = supabase.table(table).upsert(row, on_conflict=on_conflict).execute()
    if not result.data:
        _repo_logger.warning("save_report upsert returned no data (table=%s, on_conflict=%s)", table, on_conflict)


def fetch_articles_for_day(target_date: date) -> list[dict]:
    start_at, end_at = utc_day_bounds(target_date)
    result = (
        supabase.table("articles")
        .select("id, title, event_summary, article_labels(label, confidence)")
        .gte("published_at", start_at)
        .lte("published_at", end_at)
        .order("published_at", desc=True)
        .execute()
    )
    return result.data or []


def fetch_player_mentions(article_ids: list[int]) -> list[dict]:
    return _fetch_article_player_rows(article_ids, "player_id, players(name)")


def fetch_recent_player_articles(
    player_id: int,
    *,
    since: date,
    limit: int,
) -> list[dict]:
    start_at, _ = utc_day_bounds(since)
    result = (
        supabase.table("article_players")
        .select("articles!inner(title, published_at, event_summary)")
        .eq("player_id", player_id)
        .gte("articles.published_at", start_at)
        .order("articles.published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def fetch_latest_player_stats(player_id: int) -> dict:
    result = (
        supabase.table("player_stats_daily")
        .select("*")
        .eq("player_id", player_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


def list_active_players() -> list[dict]:
    # "active" is set by sync_players.py; "1\uad70" handles legacy seeds before the sync ran.
    result = (
        supabase.table("players")
        .select("id, name")
        .in_("status", ["active", "1\uad70"])
        .execute()
    )
    return result.data


def fetch_games_for_day(target_date: date) -> list[dict]:
    result = (
        supabase.table("games")
        .select("*")
        .eq("date", target_date.isoformat())
        .order("game_seq")
        .execute()
    )
    return result.data or []


def fetch_game_for_day(target_date: date) -> dict | None:
    games = fetch_games_for_day(target_date)
    return games[0] if games else None


def fetch_player_mentions_with_position(article_ids: list[int]) -> list[dict]:
    return _fetch_article_player_rows(article_ids, "player_id, players(id, name, position)")
