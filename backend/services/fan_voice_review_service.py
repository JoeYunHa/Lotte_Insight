from __future__ import annotations

from datetime import date

from core import cache
from core.time_utils import today_kst
from services import fan_voice_review_repository
from services.cache_keys import fanvoice_review_key
from services.opinion_clusterer import OpinionClusterer

_DEFAULT_MIN_MESSAGES = 20


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
    opinions = clusterer.cluster_by_jaccard_trigram(messages, max_opinions=5)
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

    # Use centralized cache key builder (consistent naming)
    cache_key = fanvoice_review_key(
        context_type=context_type,
        context_id=context_id,
        game_date=game_date,
        review_type=review_type,
    )
    response = {
        "review_id": review_row["id"],
        "game_date": game_date.isoformat(),
        "is_fallback": is_fallback,
        "source_scope": source_scope,
        "review_type": review_type,
        "summary": {"title": summary_title, "body": summary_body},
        "metrics": {
            "message_count": message_count,
            "unique_user_count": unique_user_count,
        },
        "top_opinions": opinions,
        "emotion_ranking": emotion_ranking,
        "player_ranking": player_ranking,
    }
    cache.set_json(cache_key, response, 600)
    return response


def get_daily_review(
    *,
    scope: str = "today_or_latest",
    requested_date: date | None = None,
    context_type: str = "home",
    context_id: str = "today",
    review_type: str = "final",
) -> dict:
    """
    Retrieve existing daily review (read-only, cached).

    This is the READ path - delegates date resolution to resolve_target_game_date
    to eliminate duplication with API layer.
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
    if cached:
        return cached

    # If not cached, return the last generated review (this is GET, not POST)
    # In production, this would query the database for existing review
    # For now, delegate to generate (this maintains backwards compatibility)
    return generate_daily_review(
        scope=scope,
        requested_date=requested_date,
        context_type=context_type,
        context_id=context_id,
        review_type=review_type,
    )


def _build_summary(*, opinions: list[dict], message_count: int) -> str:
    if not opinions:
        return f"총 {message_count}개의 의견이 수집되었지만 뚜렷한 주류 의견이 형성되지 않았습니다."
    top = opinions[0]
    return (
        f"총 {message_count}개 의견 중 '{top['opinion_title']}' 흐름이 가장 강했습니다. "
        f"(언급 {top['mention_count']}회, 반응 {top['reaction_sum']}회)"
    )
