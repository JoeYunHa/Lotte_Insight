from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from core.config import settings
from core.session_utils import generate_session_token, hash_session_token
from services import fan_voice_moderation, fan_voice_rate_limit, fan_voice_repository

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
_VALID_CONTEXT_TYPES = {"home", "player", "topic", "game", "label"}
_VALID_REACTION_TYPES = {"like", "fire", "agree"}
_VALID_REPORT_REASONS = {"abuse", "spam", "hate", "other"}
_MAX_DISPLAY_SECONDS = 18
_MIN_DISPLAY_SECONDS = 10
_DISPLAY_SECONDS_PER_CHAR = 0.12
_SLOW_MODE_POLL_MS = 8000
_NORMAL_MODE_POLL_MS = 5000


def _generate_alias() -> str:
    # deterministic uniqueness is not required in phase 0
    value = int(datetime.now(_KST).timestamp() * 1000) % 1000
    return f"Giants Fan {value:03d}"


def init_session(existing_token: str | None) -> tuple[str, dict]:
    if existing_token:
        token_hash = hash_session_token(existing_token)
        session = fan_voice_repository.get_session_by_hash(token_hash)
        if session:
            fan_voice_repository.touch_session(session["id"])
            return existing_token, session

    token = generate_session_token()
    token_hash = hash_session_token(token)
    session = fan_voice_repository.create_session(token_hash, _generate_alias())
    return token, session


def _validate_context(context_type: str, context_id: str) -> None:
    if context_type not in _VALID_CONTEXT_TYPES:
        raise ValueError("invalid context_type")
    if not context_id.strip():
        raise ValueError("context_id is required")


def _get_validated_session(session_token: str) -> dict:
    session = fan_voice_repository.get_session_by_hash(hash_session_token(session_token))
    if not session:
        raise ValueError("invalid session")
    if session.get("is_blocked"):
        raise PermissionError("blocked session")
    return session


def _is_enabled_context(context_type: str) -> bool:
    try:
        enabled = bool(getattr(settings, "fan_voice_enabled", True))
        if not enabled:
            return False
        contexts = getattr(settings, "fan_voice_contexts", _VALID_CONTEXT_TYPES)
        return context_type in set(contexts)
    except ModuleNotFoundError as exc:
        # Only swallow missing-config import errors; let real import bugs surface.
        logger.warning("fan voice config module missing, defaulting to enabled: %s", exc)
        return True


def _is_write_enabled() -> bool:
    try:
        return bool(getattr(settings, "fan_voice_write_enabled", True))
    except ModuleNotFoundError as exc:
        logger.warning("fan voice write config missing, defaulting to enabled: %s", exc)
        return True


def get_stream(*, context_type: str, context_id: str, limit: int = 30) -> dict:
    _validate_context(context_type, context_id)
    if not _is_enabled_context(context_type):
        raise PermissionError("fan voice context disabled")
    stream_rows = fan_voice_repository.list_stream_messages(
        context_type=context_type,
        context_id=context_id,
        limit=limit,
    )
    messages: list[dict] = []
    emotion_summary: dict[str, int] = {}
    for row in stream_rows:
        emotion = row.get("emotion_tag")
        if emotion:
            emotion_summary[emotion] = emotion_summary.get(emotion, 0) + 1
        messages.append(
            {
                "id": row["id"],
                "context_type": row["context_type"],
                "context_id": row["context_id"],
                "message": row["message"],
                "emotion_tag": row.get("emotion_tag"),
                "topic_tag": row.get("topic_tag"),
                "session_alias": ((row.get("fan_sessions") or {}).get("session_alias") or "Fan"),
                "player_id": row.get("player_id"),
                "cluster_id": row.get("cluster_id"),
                "game_date": row.get("game_date"),
                "reaction_count": row.get("reaction_count", 0),
                "report_count": row.get("report_count", 0),
                "is_highlighted": bool(row.get("pinned_score", 0) > 0),
                "display_seconds": min(
                    _MAX_DISPLAY_SECONDS,
                    max(_MIN_DISPLAY_SECONDS, int(_MIN_DISPLAY_SECONDS + len(row["message"]) * _DISPLAY_SECONDS_PER_CHAR)),
                ),
                "created_at": row["created_at"],
            }
        )

    slow_mode = fan_voice_rate_limit.detect_slow_mode(context_type, context_id)
    return {
        "messages": messages,
        "slow_mode": slow_mode,
        "presence_count": 0,
        "emotion_summary": emotion_summary,
        "next_poll_after_ms": _SLOW_MODE_POLL_MS if slow_mode else _NORMAL_MODE_POLL_MS,
    }


def create_message(
    *,
    session_token: str,
    context_type: str,
    context_id: str,
    message: str,
    emotion_tag: str | None,
    topic_tag: str | None,
    player_id: int | None,
    cluster_id: str | None,
    game_date: str | None,
) -> dict:
    _validate_context(context_type, context_id)
    if not _is_enabled_context(context_type):
        raise PermissionError("fan voice context disabled")
    if not _is_write_enabled():
        raise PermissionError("fan voice write disabled")
    text = fan_voice_moderation.normalize_message(message)
    fan_voice_moderation.validate_message(text)

    session = _get_validated_session(session_token)
    slow_mode = fan_voice_rate_limit.detect_slow_mode(context_type, context_id)
    can_write, retry_after = fan_voice_rate_limit.can_write(session["id"], slow_mode=slow_mode)
    if not can_write:
        raise PermissionError(f"rate limited; retry in {retry_after}s")
    if fan_voice_rate_limit.is_duplicate_message(session["id"], text.lower()):
        raise PermissionError("duplicate message blocked")

    created = fan_voice_repository.create_message(
        session_id=session["id"],
        context_type=context_type,
        context_id=context_id,
        message=text,
        emotion_tag=emotion_tag,
        topic_tag=topic_tag,
        player_id=player_id,
        cluster_id=cluster_id,
        game_date=game_date,
    )
    fan_voice_repository.increment_write_count(session["id"])
    fan_voice_rate_limit.mark_write(session["id"])
    fan_voice_rate_limit.mark_message(session["id"], text.lower())
    fan_voice_rate_limit.record_context_write(context_type, context_id)
    return created


def react_message(*, session_token: str, message_id: str, reaction_type: str) -> int:
    if reaction_type not in _VALID_REACTION_TYPES:
        raise ValueError("invalid reaction_type")
    session = _get_validated_session(session_token)
    return fan_voice_repository.insert_reaction(
        message_id=message_id,
        session_id=session["id"],
        reaction_type=reaction_type,
    )


def report_message(*, session_token: str, message_id: str, reason: str) -> int:
    if reason not in _VALID_REPORT_REASONS:
        raise ValueError("invalid reason")
    session = _get_validated_session(session_token)
    return fan_voice_repository.insert_report(
        message_id=message_id,
        session_id=session["id"],
        reason=reason,
    )
