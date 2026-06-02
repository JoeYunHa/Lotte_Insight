import threading
from dataclasses import dataclass

from core.database import supabase

# Process-local in-memory cache. Each Railway worker process holds its own copy;
# invalidate_cache() only affects the calling process. If multi-process deployment
# requires cross-process invalidation, migrate this cache to Redis.
_players_cache: list[dict] | None = None
_alias_index_cache: "PlayerAliasIndex | None" = None
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class PlayerAliasIndex:
    aliases_by_player_id: dict[int, tuple[str, ...]]
    player_ids_by_alias: dict[str, tuple[int, ...]]
    aliases_desc: tuple[str, ...]

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
        found: set[int] = set()
        for alias in self.aliases_desc:
            if alias in text:
                found.update(self.player_ids_by_alias.get(alias, ()))
        return list(found)


def _fetch_players() -> list[dict]:
    result = supabase.table("players").select("id, name, name_variants, status").execute()
    return result.data


def _player_aliases(player: dict) -> tuple[str, ...]:
    aliases = [player["name"], *(player.get("name_variants") or [])]
    return tuple(dict.fromkeys(alias for alias in aliases if alias))


def list_players(*, use_cache: bool = True) -> list[dict]:
    global _players_cache
    if use_cache and _players_cache is not None:
        return _players_cache
    with _cache_lock:
        if use_cache and _players_cache is not None:
            return _players_cache
        _players_cache = _fetch_players()
    return _players_cache


def build_player_alias_index(*, use_cache: bool = True) -> PlayerAliasIndex:
    global _alias_index_cache
    if use_cache and _alias_index_cache is not None:
        return _alias_index_cache
    with _cache_lock:
        if use_cache and _alias_index_cache is not None:
            return _alias_index_cache
        aliases_by_player_id = {
            player["id"]: _player_aliases(player)
            for player in list_players(use_cache=use_cache)
        }
        player_ids_by_alias: dict[str, list[int]] = {}
        for player_id, aliases in aliases_by_player_id.items():
            for alias in aliases:
                player_ids_by_alias.setdefault(alias, []).append(player_id)
        aliases_desc = tuple(sorted(player_ids_by_alias.keys(), key=len, reverse=True))
        _alias_index_cache = PlayerAliasIndex(
            aliases_by_player_id=aliases_by_player_id,
            player_ids_by_alias={k: tuple(v) for k, v in player_ids_by_alias.items()},
            aliases_desc=aliases_desc,
        )
    return _alias_index_cache


_ACTIVE_STATUSES = {"active", "1군"}


def list_player_names(*, use_cache: bool = True, active_only: bool = False) -> list[str]:
    """모든 alias(이름+변형)를 반환 — 내부 매칭용."""
    if active_only:
        players = [p for p in list_players(use_cache=use_cache) if p.get("status") in _ACTIVE_STATUSES]
        aliases_by_player_id = {p["id"]: _player_aliases(p) for p in players}
        player_ids_by_alias: dict[str, list[int]] = {}
        for player_id, aliases in aliases_by_player_id.items():
            for alias in aliases:
                player_ids_by_alias.setdefault(alias, []).append(player_id)
        return PlayerAliasIndex(
            aliases_by_player_id=aliases_by_player_id,
            player_ids_by_alias={k: tuple(v) for k, v in player_ids_by_alias.items()},
            aliases_desc=tuple(sorted(player_ids_by_alias.keys(), key=len, reverse=True)),
        ).all_names()
    return build_player_alias_index(use_cache=use_cache).all_names()


def list_player_canonical_names(*, use_cache: bool = True, active_only: bool = False) -> list[str]:
    """등록명(canonical name)만 반환 — 외부 API 검색 키워드 생성 전용.

    alias를 포함하면 중복 쿼리와 약한 별칭 기반 노이즈가 늘어나므로
    외부 수집에서는 이 함수를 사용하고, list_player_names()는 내부 매칭에만 사용한다.
    """
    players = list_players(use_cache=use_cache)
    if active_only:
        players = [p for p in players if p.get("status") in _ACTIVE_STATUSES]
    return [p["name"] for p in players if p.get("name")]


def player_name_to_id_map(*, use_cache: bool = True) -> dict[str, int]:
    return build_player_alias_index(use_cache=use_cache).name_to_id_map()


def invalidate_cache():
    global _players_cache, _alias_index_cache
    _players_cache = None
    _alias_index_cache = None
