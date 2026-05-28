from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.database import supabase

_KST = timezone(timedelta(hours=9))


def get_session_by_hash(session_token_hash: str) -> dict | None:
    result = (
        supabase.table("fan_sessions")
        .select("*")
        .eq("session_token_hash", session_token_hash)
        .maybe_single()
        .execute()
    )
    return result.data


def create_session(session_token_hash: str, session_alias: str) -> dict:
    result = (
        supabase.table("fan_sessions")
        .insert(
            {
                "session_token_hash": session_token_hash,
                "session_alias": session_alias,
            }
        )
        .execute()
    )
    return result.data[0]


def touch_session(session_id: int) -> None:
    supabase.table("fan_sessions").update({"last_seen_at": datetime.now(_KST).isoformat()}).eq(
        "id", session_id
    ).execute()


def increment_write_count(session_id: int) -> None:
    supabase.rpc("increment_fan_session_write_count", {"p_session_id": session_id}).execute()


def create_message(
    *,
    session_id: int,
    context_type: str,
    context_id: str,
    message: str,
    emotion_tag: str | None,
    topic_tag: str | None,
    player_id: int | None,
    cluster_id: str | None,
    game_date: str | None,
    expires_hours: int = 48,
) -> dict:
    expires_at = datetime.now(_KST) + timedelta(hours=expires_hours)
    result = (
        supabase.table("fan_voice_messages")
        .insert(
            {
                "session_id": session_id,
                "context_type": context_type,
                "context_id": context_id,
                "message": message,
                "emotion_tag": emotion_tag,
                "topic_tag": topic_tag,
                "player_id": player_id,
                "cluster_id": cluster_id,
                "game_date": game_date,
                "status": "visible",
                "expires_at": expires_at.isoformat(),
            }
        )
        .execute()
    )
    return result.data[0]


def list_stream_messages(*, context_type: str, context_id: str, limit: int) -> list[dict]:
    result = (
        supabase.table("fan_voice_messages")
        .select(
            "id,context_type,context_id,message,emotion_tag,topic_tag,player_id,cluster_id,game_date,"
            "reaction_count,report_count,pinned_score,created_at,fan_sessions(session_alias)"
        )
        .eq("context_type", context_type)
        .eq("context_id", context_id)
        .eq("status", "visible")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def insert_reaction(*, message_id: str, session_id: int, reaction_type: str) -> int:
    result = supabase.rpc(
        "apply_fan_voice_reaction",
        {
            "p_message_id": message_id,
            "p_session_id": session_id,
            "p_reaction_type": reaction_type,
        },
    ).execute()
    return int(result.data or 0)


def insert_report(*, message_id: str, session_id: int, reason: str) -> int:
    result = supabase.rpc(
        "apply_fan_voice_report",
        {
            "p_message_id": message_id,
            "p_session_id": session_id,
            "p_reason": reason,
        },
    ).execute()
    return int(result.data or 0)
