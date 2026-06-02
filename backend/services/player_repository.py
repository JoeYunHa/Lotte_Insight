from datetime import date

from core import cache
from core.config import settings
from core.database import supabase
from core.time_utils import today_kst
from services.cache_keys import CacheKeyBuilder

# KBO crawler runs every 2 hours — roster data stays fresh within that window.
_PLAYER_LIST_TTL = 7200


def list_players(*, status: str | None = None) -> list[dict]:
    cache_key = CacheKeyBuilder.player_list(status=status)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    query = supabase.table("players").select("id, name, position, status")
    if status:
        query = query.eq("status", status)
    result = query.order("name").execute()
    data = result.data or []

    cache.set_json(cache_key, data, _PLAYER_LIST_TTL)
    return data


def get_player(player_id: int, *, stats_date: date | None = None) -> dict | None:
    cache_key = CacheKeyBuilder.player_detail(player_id=player_id, stats_date=stats_date)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

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

    # Stats are updated daily; cache until KST midnight.
    ttl_date = stats_date if stats_date else today_kst()
    cache.set_json(cache_key, player, cache.ttl_seconds(ttl_date))
    return player
