from datetime import date

from core.config import settings
from core.database import supabase


def list_players(*, status: str | None = None) -> list[dict]:
    query = supabase.table("players").select("id, name, position, status")
    if status:
        query = query.eq("status", status)
    result = query.order("name").execute()
    return result.data


def get_player(player_id: int, *, stats_date: date | None = None) -> dict | None:
    player_result = (
        supabase.table("players")
        .select("id, name, position, status, name_variants")
        .eq("id", player_id)
        .maybe_single()
        .execute()
    )
    if not player_result.data:
        return None

    player = dict(player_result.data)
    stats_query = supabase.table("player_stats_daily").select("*").eq("player_id", player_id)
    if stats_date:
        stats_query = stats_query.eq("date", stats_date.isoformat())
    else:
        stats_query = stats_query.order("date", desc=True).limit(
            settings.player_stats_history_limit
        )
    player["stats"] = stats_query.execute().data
    return player
