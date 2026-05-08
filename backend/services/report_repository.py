from datetime import date

from core.database import supabase
from core.time_utils import utc_day_bounds


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
    return result.data


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


def save_report(table: str, row: dict, *, on_conflict: str) -> None:
    supabase.table(table).upsert(row, on_conflict=on_conflict).execute()


def fetch_articles_for_day(target_date: date) -> list[dict]:
    start_at, end_at = utc_day_bounds(target_date)
    result = (
        supabase.table("articles")
        .select("id, article_labels(label)")
        .gte("published_at", start_at)
        .lte("published_at", end_at)
        .execute()
    )
    return result.data


def fetch_player_mentions(article_ids: list[int]) -> list[dict]:
    if not article_ids:
        return []
    result = (
        supabase.table("article_players")
        .select("player_id, players(name)")
        .in_("article_id", article_ids)
        .execute()
    )
    return result.data


def fetch_recent_player_articles(
    player_id: int,
    *,
    since: date,
    limit: int,
) -> list[dict]:
    result = (
        supabase.table("article_players")
        .select("articles!inner(title, published_at, event_summary)")
        .eq("player_id", player_id)
        .gte("articles.published_at", f"{since.isoformat()}T00:00:00")
        .order("articles.published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


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
    result = supabase.table("players").select("id, name").eq("status", "active").execute()
    return result.data
