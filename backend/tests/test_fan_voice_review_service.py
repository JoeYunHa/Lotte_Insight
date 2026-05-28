from datetime import date
from unittest.mock import patch

import pytest

from services import fan_voice_review_service


def test_resolve_target_game_date_returns_today_when_game_exists():
    with (
        patch("services.fan_voice_review_service.today_kst", return_value=date(2026, 5, 28)),
        patch("services.fan_voice_review_service.fan_voice_review_repository.game_exists", return_value=True),
    ):
        target, is_fallback, source_scope = fan_voice_review_service.resolve_target_game_date(
            scope="today_or_latest"
        )
    assert target == date(2026, 5, 28)
    assert is_fallback is False
    assert source_scope == "today"


def test_resolve_target_game_date_falls_back_to_latest():
    with (
        patch("services.fan_voice_review_service.today_kst", return_value=date(2026, 5, 28)),
        patch("services.fan_voice_review_service.fan_voice_review_repository.game_exists", return_value=False),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.latest_game_date",
            return_value=date(2026, 5, 27),
        ),
    ):
        target, is_fallback, source_scope = fan_voice_review_service.resolve_target_game_date(
            scope="today_or_latest"
        )
    assert target == date(2026, 5, 27)
    assert is_fallback is True
    assert source_scope == "latest_fallback"


def test_resolve_target_game_date_rejects_missing_date_for_scope_date():
    with pytest.raises(ValueError):
        fan_voice_review_service.resolve_target_game_date(scope="date")


def test_generate_daily_review_returns_insufficient_data():
    with (
        patch(
            "services.fan_voice_review_service.resolve_target_game_date",
            return_value=(date(2026, 5, 28), False, "today"),
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.fetch_messages_for_review",
            return_value=[{"id": "1", "session_id": 1}],
        ),
    ):
        result = fan_voice_review_service.generate_daily_review(min_messages=2)

    assert result["status"] == "insufficient_data"
    assert result["message_count"] == 1


def test_generate_daily_review_persists_and_returns_payload():
    messages = [
        {
            "id": "1",
            "session_id": 1,
            "message": "불펜 운용 아쉽다",
            "reaction_count": 2,
            "emotion_tag": "frustrated",
        },
        {
            "id": "2",
            "session_id": 2,
            "message": "불펜 운용 아쉽다",
            "reaction_count": 1,
            "emotion_tag": "disappointed",
        },
    ]
    with (
        patch(
            "services.fan_voice_review_service.resolve_target_game_date",
            return_value=(date(2026, 5, 28), False, "today"),
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.fetch_messages_for_review",
            return_value=messages,
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.aggregate_emotion_ranking",
            return_value=[{"emotion_tag": "frustrated", "mention_count": 2}],
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.aggregate_player_ranking",
            return_value=[],
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.upsert_daily_review",
            return_value={"id": 11},
        ) as mock_upsert,
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.replace_daily_opinions"
        ) as mock_replace,
        patch("services.fan_voice_review_service.cache.set_json") as mock_cache_set,
    ):
        result = fan_voice_review_service.generate_daily_review(min_messages=2)

    assert result["review_id"] == 11
    assert result["metrics"]["message_count"] == 2
    assert len(result["top_opinions"]) == 1
    mock_upsert.assert_called_once()
    mock_replace.assert_called_once()
    mock_cache_set.assert_called_once()
