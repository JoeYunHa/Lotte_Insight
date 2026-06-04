import logging
import threading
from dataclasses import dataclass

from core.database import supabase

logger = logging.getLogger(__name__)

# Process-local in-memory cache. Each Railway worker process holds its own copy;
# invalidate_cache() only affects the calling process. If multi-process deployment
# requires cross-process invalidation, migrate this cache to Redis.
_players_cache: list[dict] | None = None
_alias_index_cache: "PlayerAliasIndex | None" = None
_nicknames_cache: "dict[int, list[str]] | None" = None
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


def _fetch_player_nicknames() -> dict[int, list[str]]:
    global _nicknames_cache
    if _nicknames_cache is not None:
        return _nicknames_cache
    with _cache_lock:
        if _nicknames_cache is not None:
            return _nicknames_cache
        try:
            result = supabase.table("player_nicknames").select("player_id, nickname").execute()
        except Exception as exc:
            logger.warning("Failed to fetch player_nicknames: %s", exc, exc_info=True)
            return {}
        nicknames: dict[int, list[str]] = {}
        for row in result.data or []:
            player_id = row.get("player_id")
            nickname = row.get("nickname")
            if player_id and nickname:
                nicknames.setdefault(player_id, []).append(nickname)
        _nicknames_cache = nicknames
    return _nicknames_cache


def _player_aliases(player: dict) -> tuple[str, ...]:
    aliases = [
        player["name"],
        *(player.get("name_variants") or []),
        *(player.get("nicknames") or []),
    ]
    return tuple(dict.fromkeys(alias for alias in aliases if alias))


def _attach_nicknames(players: list[dict]) -> list[dict]:
    nicknames_by_player_id = _fetch_player_nicknames()
    if not nicknames_by_player_id:
        return players
    enriched: list[dict] = []
    for player in players:
        cloned = dict(player)
        cloned["nicknames"] = nicknames_by_player_id.get(player.get("id"), [])
        enriched.append(cloned)
    return enriched


def _build_alias_index_from_players(players: list[dict]) -> PlayerAliasIndex:
    players = _attach_nicknames(players)
    aliases_by_player_id = {
        player["id"]: _player_aliases(player)
        for player in players
    }
    player_ids_by_alias: dict[str, list[int]] = {}
    for player_id, aliases in aliases_by_player_id.items():
        for alias in aliases:
            player_ids_by_alias.setdefault(alias, []).append(player_id)
    return PlayerAliasIndex(
        aliases_by_player_id=aliases_by_player_id,
        player_ids_by_alias={k: tuple(v) for k, v in player_ids_by_alias.items()},
        aliases_desc=tuple(sorted(player_ids_by_alias.keys(), key=len, reverse=True)),
    )


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
        _alias_index_cache = _build_alias_index_from_players(list_players(use_cache=use_cache))
    return _alias_index_cache


_ACTIVE_STATUSES = {"active", "1군"}


def get_active_player_ids(*, use_cache: bool = True) -> frozenset[int]:
    return frozenset(
        p["id"]
        for p in list_players(use_cache=use_cache)
        if p.get("status") in _ACTIVE_STATUSES
    )


def list_player_names(*, use_cache: bool = True, active_only: bool = False) -> list[str]:
    """모든 alias(이름+변형)를 반환 — 내부 매칭용."""
    if active_only:
        players = [p for p in list_players(use_cache=use_cache) if p.get("status") in _ACTIVE_STATUSES]
        return _build_alias_index_from_players(players).all_names()
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
    global _players_cache, _alias_index_cache, _nicknames_cache
    _players_cache = None
    _alias_index_cache = None
    _nicknames_cache = None
