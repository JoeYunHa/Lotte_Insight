from core.database import supabase

_players_cache: list[dict] | None = None


def _fetch_players() -> list[dict]:
    result = supabase.table("players").select("id, name, name_variants").execute()
    return result.data


def list_players(*, use_cache: bool = True) -> list[dict]:
    global _players_cache
    if not use_cache or _players_cache is None:
        _players_cache = _fetch_players()
    return _players_cache


def list_player_names(*, use_cache: bool = True) -> list[str]:
    names: list[str] = []
    for player in list_players(use_cache=use_cache):
        names.append(player["name"])
        names.extend(player.get("name_variants") or [])
    return names


def player_name_to_id_map(*, use_cache: bool = True) -> dict[str, int]:
    name_map: dict[str, int] = {}
    for player in list_players(use_cache=use_cache):
        name_map[player["name"]] = player["id"]
        for variant in player.get("name_variants") or []:
            name_map[variant] = player["id"]
    return name_map


def invalidate_cache():
    global _players_cache
    _players_cache = None
