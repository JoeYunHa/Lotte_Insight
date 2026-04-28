from core.database import supabase

_players_cache: list[dict] | None = None


def _load_players() -> list[dict]:
    global _players_cache
    if _players_cache is None:
        result = supabase.table("players").select("id, name, name_variants").execute()
        _players_cache = result.data
    return _players_cache


def invalidate_cache():
    global _players_cache
    _players_cache = None


def extract_players(title: str) -> list[int]:
    """기사 제목에서 선수 ID 목록을 반환."""
    players = _load_players()
    found: list[int] = []
    for player in players:
        names = [player["name"]] + (player.get("name_variants") or [])
        if any(name in title for name in names):
            found.append(player["id"])
    return found
