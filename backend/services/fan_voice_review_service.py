from __future__ import annotations

from datetime import date

from core import cache
from core.time_utils import today_kst
from services import fan_voice_review_repository
from services.cache_keys import fanvoice_review_key
from services.opinion_clusterer import OpinionClusterer

_DEFAULT_MIN_MESSAGES = 20
_NULL_SENTINEL = {"_null_result": True}
_NULL_RESULT_TTL = 60  # seconds — cache "no review" to avoid repeated DB round-trips


def resolve_target_game_date(
    *, scope: str, requested_date: date | None = None, now_date: date | None = None
) -> tuple[date, bool, str]:
    if scope == "date":
        if requested_date is None:
            raise ValueError("date is required when scope=date")
        return requested_date, False, "today"
    if scope != "today_or_latest":
        raise ValueError("invalid scope")

    today = now_date or today_kst()
    if fan_voice_review_repository.game_exists(today):
        return today, False, "today"

    latest = fan_voice_review_repository.latest_game_date(today)
    if latest is None:
        raise ValueError("no game data available")
    return latest, True, "latest_fallback"


def generate_daily_review(
    *,
    scope: str = "today_or_latest",
    requested_date: date | None = None,
    context_type: str = "home",
    context_id: str = "today",
    review_type: str = "final",
    min_messages: int = _DEFAULT_MIN_MESSAGES,
) -> dict:
    game_date, is_fallback, source_scope = resolve_target_game_date(
        scope=scope, requested_date=requested_date
    )
    messages = fan_voice_review_repository.fetch_messages_for_review(
        game_date=game_date,
        context_type=context_type,
        context_id=context_id,
    )
    message_count = len(messages)
    unique_user_count = len({m.get("session_id") for m in messages if m.get("session_id")})
    if message_count < min_messages:
        return {
            "game_date": game_date.isoformat(),
            "is_fallback": is_fallback,
            "source_scope": source_scope,
            "status": "insufficient_data",
            "message_count": message_count,
            "unique_user_count": unique_user_count,
        }

    clusterer = OpinionClusterer()
    # Cap clustering input to avoid O(N^2) blowups on viral days. We keep the
    # most-reacted messages so the dominant opinions still surface.
    _MAX_CLUSTER_INPUT = 2000
    clustering_input = sorted(
        messages,
        key=lambda m: int(m.get("reaction_count") or 0),
        reverse=True,
    )[:_MAX_CLUSTER_INPUT]
    opinions = clusterer.cluster_by_jaccard_trigram(clustering_input, max_opinions=5)
    emotion_ranking = fan_voice_review_repository.aggregate_emotion_ranking(
        game_date=game_date,
        context_type=context_type,
        context_id=context_id,
        limit=5,
    )
    player_ranking = fan_voice_review_repository.aggregate_player_ranking(
        game_date=game_date,
        context_type=context_type,
        context_id=context_id,
        limit=10,
    )

    summary_title = "오늘 팬 여론 요약"
    summary_body = _build_summary(opinions=opinions, message_count=message_count)
    review_row = fan_voice_review_repository.upsert_daily_review(
        {
            "game_date": game_date.isoformat(),
            "context_key": f"{context_type}:{context_id}",
            "source_scope": source_scope,
            "message_count": message_count,
            "unique_user_count": unique_user_count,
            "summary_title": summary_title,
            "summary_body": summary_body,
            "highlights": [],
            "caution_notes": [],
            "review_type": review_type,
            "generation_status": "completed",
        }
    )
    fan_voice_review_repository.replace_daily_opinions(
        review_id=review_row["id"],
        opinions=opinions,
    )

    cache_key = fanvoice_review_key(
        context_type=context_type,
        context_id=context_id,
        game_date=game_date,
        review_type=review_type,
    )
    response = _build_review_response(
        review_id=review_row["id"],
        game_date=game_date,
        is_fallback=is_fallback,
        source_scope=source_scope,
        review_type=review_type,
        summary_title=summary_title,
        summary_body=summary_body,
        message_count=message_count,
        unique_user_count=unique_user_count,
        top_opinions=opinions,
        emotion_ranking=emotion_ranking,
        player_ranking=player_ranking,
    )
    cache.set_json(cache_key, response, cache.ttl_seconds(game_date))
    return response


def get_daily_review(
    *,
    scope: str = "today_or_latest",
    requested_date: date | None = None,
    context_type: str = "home",
    context_id: str = "today",
    review_type: str = "final",
) -> dict | None:
    """
    Retrieve existing daily review (READ-only, cached).

    This is a pure read path. On cache miss, it queries the database for an
    existing review. If no review exists, returns None — the caller is
    responsible for handling absence (e.g. 404). Generation is only performed
    by the batch path via `generate_daily_review`.
    """
    # Delegate date resolution to service layer (no duplication)
    game_date, is_fallback, source_scope = resolve_target_game_date(
        scope=scope, requested_date=requested_date
    )

    # Use centralized cache key builder (consistent naming)
    cache_key = fanvoice_review_key(
        context_type=context_type,
        context_id=context_id,
        game_date=game_date,
        review_type=review_type,
    )

    # Try cache first
    cached = cache.get_json(cache_key)
    if cached is not None:
        if cached == _NULL_SENTINEL:
            return None
        return cached

    # Cache miss → read existing review from DB (NEVER write here).
    context_key = f"{context_type}:{context_id}"
    review_row = fan_voice_review_repository.fetch_daily_review(
        game_date=game_date,
        context_key=context_key,
        review_type=review_type,
    )
    if review_row is None:
        # Cache the absence so repeated 404s skip the DB.
        cache.set_json(cache_key, _NULL_SENTINEL, _NULL_RESULT_TTL)
        return None

    opinions = fan_voice_review_repository.fetch_daily_opinions(
        review_id=review_row["id"]
    )
    emotion_ranking = fan_voice_review_repository.aggregate_emotion_ranking(
        game_date=game_date,
        context_type=context_type,
        context_id=context_id,
        limit=5,
    )
    player_ranking = fan_voice_review_repository.aggregate_player_ranking(
        game_date=game_date,
        context_type=context_type,
        context_id=context_id,
        limit=10,
    )

    response = _build_review_response(
        review_id=review_row["id"],
        game_date=game_date,
        is_fallback=is_fallback,
        source_scope=source_scope,
        review_type=review_type,
        summary_title=review_row.get("summary_title"),
        summary_body=review_row.get("summary_body"),
        message_count=review_row.get("message_count", 0),
        unique_user_count=review_row.get("unique_user_count", 0),
        top_opinions=opinions,
        emotion_ranking=emotion_ranking,
        player_ranking=player_ranking,
    )
    cache.set_json(cache_key, response, cache.ttl_seconds(game_date))
    return response


def _build_review_response(
    *,
    review_id: str,
    game_date: date,
    is_fallback: bool,
    source_scope: str,
    review_type: str,
    summary_title: str | None,
    summary_body: str | None,
    message_count: int,
    unique_user_count: int,
    top_opinions: list[dict],
    emotion_ranking: list[dict],
    player_ranking: list[dict],
) -> dict:
    return {
        "review_id": review_id,
        "game_date": game_date.isoformat(),
        "is_fallback": is_fallback,
        "source_scope": source_scope,
        "review_type": review_type,
        "summary": {"title": summary_title, "body": summary_body},
        "metrics": {
            "message_count": message_count,
            "unique_user_count": unique_user_count,
        },
        "top_opinions": top_opinions,
        "emotion_ranking": emotion_ranking,
        "player_ranking": player_ranking,
    }


def _build_summary(*, opinions: list[dict], message_count: int) -> str:
    if not opinions:
        return f"총 {message_count}개의 의견이 수집되었지만 뚜렷한 주류 의견이 형성되지 않았습니다."
    top = opinions[0]
    return (
        f"총 {message_count}개 의견 중 '{top['opinion_title']}' 흐름이 가장 강했습니다. "
        f"(언급 {top['mention_count']}회, 반응 {top['reaction_sum']}회)"
    )


def _ranking_envelope(target_date: date, is_fallback: bool, source_scope: str, ranking: list[dict]) -> dict:
    return {
        "game_date": target_date.isoformat(),
        "is_fallback": is_fallback,
        "source_scope": source_scope,
        "ranking": ranking,
    }


def get_emotion_ranking(
    *,
    scope: str = "today_or_latest",
    requested_date: date | None = None,
    context_type: str = "home",
    context_id: str = "today",
    min_mentions: int = 0,
    limit: int = 5,
) -> dict:
    game_date, is_fallback, source_scope = resolve_target_game_date(
        scope=scope, requested_date=requested_date
    )
    ranking = fan_voice_review_repository.aggregate_emotion_ranking(
        game_date=game_date,
        context_type=context_type,
        context_id=context_id,
        min_mentions=min_mentions,
        limit=limit,
    )
    return _ranking_envelope(game_date, is_fallback, source_scope, ranking)


def get_player_ranking(
    *,
    scope: str = "today_or_latest",
    requested_date: date | None = None,
    context_type: str = "home",
    context_id: str = "today",
    min_mentions: int = 0,
    limit: int = 10,
    sentiment_filter: str | None = None,
) -> dict:
    game_date, is_fallback, source_scope = resolve_target_game_date(
        scope=scope, requested_date=requested_date
    )
    ranking = fan_voice_review_repository.aggregate_player_ranking(
        game_date=game_date,
        context_type=context_type,
        context_id=context_id,
        min_mentions=min_mentions,
        limit=limit,
        sentiment_filter=sentiment_filter,
    )
    return _ranking_envelope(game_date, is_fallback, source_scope, ranking)
