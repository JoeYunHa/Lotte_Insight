from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

from services import fan_voice_review_service


def _sample_messages() -> list[dict]:
    return [
        {
            "id": "m1",
            "session_id": 1,
            "message": "불펜 운용 아쉽다",
            "normalized_message": "불펜 운용 아쉽다",
            "reaction_count": 2,
            "emotion_tag": "frustrated",
            "primary_player_id": None,
        },
        {
            "id": "m2",
            "session_id": 2,
            "message": "불펜 운용 아쉽다",
            "normalized_message": "불펜 운용 아쉽다",
            "reaction_count": 1,
            "emotion_tag": "disappointed",
            "primary_player_id": None,
        },
    ]


def test_e2e_generate_then_payload_shape():
    with (
        patch(
            "services.fan_voice_review_service.resolve_target_game_date",
            return_value=(date(2026, 5, 28), False, "today"),
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.fetch_messages_for_review",
            return_value=_sample_messages(),
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.aggregate_emotion_ranking",
            return_value=[{"emotion_tag": "frustrated", "mention_count": 2, "reaction_sum": 3, "score": 3.0}],
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.aggregate_player_ranking",
            return_value=[],
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.upsert_daily_review",
            return_value={"id": 101},
        ),
        patch("services.fan_voice_review_service.fan_voice_review_repository.replace_daily_opinions"),
        patch("services.fan_voice_review_service.cache.set_json"),
    ):
        result = fan_voice_review_service.generate_daily_review(min_messages=2)

    assert result["review_id"] == 101
    assert result["game_date"] == "2026-05-28"
    assert isinstance(result["top_opinions"], list)
    assert isinstance(result["emotion_ranking"], list)


def test_e2e_non_game_day_fallback_to_latest():
    with (
        patch("services.fan_voice_review_service.today_kst", return_value=date(2026, 5, 28)),
        patch("services.fan_voice_review_service.fan_voice_review_repository.game_exists", return_value=False),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.latest_game_date",
            return_value=date(2026, 5, 27),
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.fetch_messages_for_review",
            return_value=[{"id": "m1", "session_id": 1}],
        ),
    ):
        result = fan_voice_review_service.generate_daily_review(min_messages=2)

    assert result["status"] == "insufficient_data"
    assert result["is_fallback"] is True
    assert result["source_scope"] == "latest_fallback"
    assert result["game_date"] == "2026-05-27"


def test_e2e_insufficient_data_response():
    with (
        patch(
            "services.fan_voice_review_service.resolve_target_game_date",
            return_value=(date(2026, 5, 28), False, "today"),
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.fetch_messages_for_review",
            return_value=[{"id": "x", "session_id": 1}],
        ),
    ):
        result = fan_voice_review_service.generate_daily_review(min_messages=20)

    assert result["status"] == "insufficient_data"
    assert result["message_count"] == 1


def test_e2e_concurrent_generation_runs_without_crash():
    with (
        patch(
            "services.fan_voice_review_service.resolve_target_game_date",
            return_value=(date(2026, 5, 28), False, "today"),
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.fetch_messages_for_review",
            return_value=_sample_messages(),
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.aggregate_emotion_ranking",
            return_value=[],
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.aggregate_player_ranking",
            return_value=[],
        ),
        patch(
            "services.fan_voice_review_service.fan_voice_review_repository.upsert_daily_review",
            return_value={"id": 201},
        ),
        patch("services.fan_voice_review_service.fan_voice_review_repository.replace_daily_opinions"),
        patch("services.fan_voice_review_service.cache.set_json"),
    ):
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(fan_voice_review_service.generate_daily_review, min_messages=2) for _ in range(2)]
            results = [f.result() for f in futures]

    assert all(item["review_id"] == 201 for item in results)
