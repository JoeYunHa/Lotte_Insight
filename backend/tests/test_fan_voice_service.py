from unittest.mock import patch

import pytest

from services import fan_voice_service


def test_get_stream_returns_slow_mode_true_when_rate_limit_detects():
    with (
        patch("services.fan_voice_service.fan_voice_rate_limit.detect_slow_mode", return_value=True),
        patch("services.fan_voice_service.fan_voice_repository.list_stream_messages", return_value=[]),
    ):
        stream = fan_voice_service.get_stream(context_type="home", context_id="today", limit=10)
    assert stream["slow_mode"] is True
    assert stream["next_poll_after_ms"] == 8000


def test_create_message_rejects_duplicate_message():
    session = {"id": 1, "is_blocked": False}
    with (
        patch("services.fan_voice_service.fan_voice_repository.get_session_by_hash", return_value=session),
        patch("services.fan_voice_service.fan_voice_rate_limit.detect_slow_mode", return_value=False),
        patch("services.fan_voice_service.fan_voice_rate_limit.can_write", return_value=(True, 0)),
        patch("services.fan_voice_service.fan_voice_rate_limit.is_duplicate_message", return_value=True),
    ):
        with pytest.raises(PermissionError):
            fan_voice_service.create_message(
                session_token="token",
                context_type="home",
                context_id="today",
                message="same message",
                emotion_tag=None,
                topic_tag=None,
                player_id=None,
                cluster_id=None,
                game_date=None,
            )


def test_create_message_blocks_when_context_disabled():
    with patch("services.fan_voice_service._is_enabled_context", return_value=False):
        with pytest.raises(PermissionError):
            fan_voice_service.create_message(
                session_token="token",
                context_type="topic",
                context_id="c01",
                message="hello",
                emotion_tag=None,
                topic_tag=None,
                player_id=None,
                cluster_id=None,
                game_date=None,
            )
