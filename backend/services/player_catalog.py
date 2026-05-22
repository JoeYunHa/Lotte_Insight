from dataclasses import dataclass

from core.database import supabase

_players_cache: list[dict] | None = None
_alias_index_cache: "PlayerAliasIndex | None" = None


@dataclass(frozen=True)
class PlayerAliasIndex:
    aliases_by_player_id: dict[int, tuple[str, ...]]

    def all_names(self) -> list[str]:
        names: list[str] = []
        for aliases in self.aliases_by_player_id.values():
            names.extend(aliases)
        return names

    def name_to_id_map(self) -> dict[str, int]:
        name_map: dict[str, int] = {}
        for player_id, aliases in self.aliases_by_player_id.items():
            for alias in aliases:
                name_map[alias] = player_id
        return name_map

    def match_player_ids(self, text: str) -> list[int]:
        found: list[int] = []
        for player_id, aliases in self.aliases_by_player_id.items():
            if any(alias in text for alias in aliases):
                found.append(player_id)
        return found


def _fetch_players() -> list[dict]:
    result = supabase.table("players").select("id, name, name_variants, status").execute()
    return result.data


def _player_aliases(player: dict) -> tuple[str, ...]:
    aliases = [player["name"], *(player.get("name_variants") or [])]
    return tuple(dict.fromkeys(alias for alias in aliases if alias))


def list_players(*, use_cache: bool = True) -> list[dict]:
    global _players_cache
    if not use_cache or _players_cache is None:
        _players_cache = _fetch_players()
    return _players_cache


def build_player_alias_index(*, use_cache: bool = True) -> PlayerAliasIndex:
    global _alias_index_cache
    if not use_cache or _alias_index_cache is None:
        _alias_index_cache = PlayerAliasIndex(
            aliases_by_player_id={
                player["id"]: _player_aliases(player)
                for player in list_players(use_cache=use_cache)
            }
        )
    return _alias_index_cache


_ACTIVE_STATUSES = {"active", "1군"}


def list_player_names(*, use_cache: bool = True, active_only: bool = False) -> list[str]:
    players = list_players(use_cache=use_cache)
    if active_only:
        players = [p for p in players if p.get("status") in _ACTIVE_STATUSES]
    return PlayerAliasIndex(
        aliases_by_player_id={p["id"]: _player_aliases(p) for p in players}
    ).all_names()


def player_name_to_id_map(*, use_cache: bool = True) -> dict[str, int]:
    return build_player_alias_index(use_cache=use_cache).name_to_id_map()


def invalidate_cache():
    global _players_cache, _alias_index_cache
    _players_cache = None
    _alias_index_cache = None
