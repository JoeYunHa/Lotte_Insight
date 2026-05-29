from __future__ import annotations

from datetime import date

from core.database import supabase


def game_exists(target_date: date) -> bool:
    result = (
        supabase.table("games").select("date").eq("date", target_date.isoformat()).limit(1).execute()
    )
    return bool(result.data)


def latest_game_date(on_or_before: date) -> date | None:
    result = (
        supabase.table("games")
        .select("date")
        .lte("date", on_or_before.isoformat())
        .order("date", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return None
    return date.fromisoformat(rows[0]["date"])


def fetch_messages_for_review(*, game_date: date, context_type: str, context_id: str) -> list[dict]:
    result = (
        supabase.table("fan_voice_messages")
        .select(
            "id,session_id,message,normalized_message,emotion_tag,reaction_count,primary_player_id,"
            "quality_score,created_at"
        )
        .eq("game_date", game_date.isoformat())
        .eq("context_type", context_type)
        .eq("context_id", context_id)
        .eq("status", "visible")
        .eq("is_duplicate", False)
        .order("created_at", desc=False)
        .limit(5000)
        .execute()
    )
    return result.data or []


def aggregate_emotion_ranking(
    *, game_date: date, context_type: str, context_id: str, min_mentions: int = 0, limit: int = 5
) -> list[dict]:
    result = supabase.rpc(
        "aggregate_emotion_ranking",
        {
            "p_game_date": game_date.isoformat(),
            "p_context_type": context_type,
            "p_context_id": context_id,
            "p_min_mentions": min_mentions,
            "p_limit": limit,
        },
    ).execute()
    return result.data or []


def aggregate_player_ranking(
    *,
    game_date: date,
    context_type: str,
    context_id: str,
    min_mentions: int = 0,
    limit: int = 10,
    sentiment_filter: str | None = None,
) -> list[dict]:
    result = supabase.rpc(
        "aggregate_player_ranking",
        {
            "p_game_date": game_date.isoformat(),
            "p_context_type": context_type,
            "p_context_id": context_id,
            "p_min_mentions": min_mentions,
            "p_limit": limit,
            "p_sentiment_filter": sentiment_filter,
        },
    ).execute()
    return result.data or []


def fetch_daily_review(
    *, game_date: date, context_key: str, review_type: str
) -> dict | None:
    """Read an existing daily review row (read-only path for GET)."""
    result = (
        supabase.table("fan_voice_daily_reviews")
        .select("*")
        .eq("game_date", game_date.isoformat())
        .eq("context_key", context_key)
        .eq("review_type", review_type)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def fetch_daily_opinions(*, review_id: int) -> list[dict]:
    """Read opinions for a given review (read-only path for GET)."""
    result = (
        supabase.table("fan_voice_daily_opinions")
        .select("*")
        .eq("review_id", review_id)
        .order("score", desc=True)
        .execute()
    )
    return result.data or []


def upsert_daily_review(payload: dict) -> dict:
    """
    Upsert a daily review record.

    Raises:
        RuntimeError: If upsert fails or returns no data
    """
    result = (
        supabase.table("fan_voice_daily_reviews")
        .upsert(payload, on_conflict="game_date,context_key,review_type")
        .execute()
    )
    if not result.data:
        raise RuntimeError(
            f"Failed to upsert review for game_date={payload.get('game_date')}, "
            f"context_key={payload.get('context_key')}"
        )
    return result.data[0]


def replace_daily_opinions(*, review_id: int, opinions: list[dict]) -> None:
    """
    Replace all opinions for a review in a single transaction.
    Uses RPC to ensure atomicity (no data loss if insert fails).
    """
    # Convert opinions to JSONB format for RPC
    opinions_json = [
        {
            "cluster_key": op["cluster_key"],
            "opinion_title": op["opinion_title"],
            "representative_message": op["representative_message"],
            "mention_count": op["mention_count"],
            "reaction_sum": op["reaction_sum"],
            "score": op["score"],
            "sentiment_hint": op.get("sentiment_hint"),
            "primary_player_id": str(op["primary_player_id"]) if op.get("primary_player_id") else None,
            "evidence_message_ids": op["evidence_message_ids"],
            "evidence_count": op["evidence_count"],
        }
        for op in opinions
    ]

    supabase.rpc(
        "replace_daily_opinions",
        {"p_review_id": review_id, "p_opinions": opinions_json},
    ).execute()

