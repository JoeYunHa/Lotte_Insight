import asyncio
from unittest.mock import patch

import httpx


class _SyncASGIClient:
    def __init__(self, app) -> None:
        self._app = app

    def _run(self, method: str, path: str, **kwargs):
        async def _req():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self._app),
                base_url="http://testserver",
            ) as ac:
                return await ac.request(method, path, **kwargs)

        return asyncio.run(_req())

    def get(self, path: str, **kwargs):
        return self._run("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self._run("POST", path, **kwargs)


def _client():
    from main import app

    return _SyncASGIClient(app)


def test_get_opinion_review_ok():
    client = _client()
    payload = {"review_id": 1, "summary": {"title": "t", "body": "b"}}
    # GET /opinion-review now calls get_daily_review (not generate_daily_review)
    with patch("api.fan_voice_review.fan_voice_review_service.get_daily_review", return_value=payload):
        res = client.get("/fan-voice/opinion-review")
    assert res.status_code == 200
    assert res.json()["review_id"] == 1


def test_get_emotions_ranking_ok():
    client = _client()
    with (
        patch(
            "api.fan_voice_review.fan_voice_review_service.resolve_target_game_date",
            return_value=(__import__("datetime").date(2026, 5, 28), False, "today"),
        ),
        patch(
            "api.fan_voice_review.fan_voice_review_service.fan_voice_review_repository.aggregate_emotion_ranking",
            return_value=[{"emotion_tag": "excited", "mention_count": 3}],
        ),
    ):
        res = client.get("/fan-voice/emotions/ranking")
    assert res.status_code == 200
    assert res.json()["ranking"][0]["emotion_tag"] == "excited"


def test_get_players_ranking_ok():
    client = _client()
    with (
        patch(
            "api.fan_voice_review.fan_voice_review_service.resolve_target_game_date",
            return_value=(__import__("datetime").date(2026, 5, 28), False, "today"),
        ),
        patch(
            "api.fan_voice_review.fan_voice_review_service.fan_voice_review_repository.aggregate_player_ranking",
            return_value=[{"player_id": 7, "mention_count": 2}],
        ),
    ):
        res = client.get("/fan-voice/players/ranking")
    assert res.status_code == 200
    assert res.json()["ranking"][0]["player_id"] == 7


def test_post_generate_opinion_review_ok():
    client = _client()
    with patch(
        "api.fan_voice_review.fan_voice_review_service.generate_daily_review",
        return_value={"review_id": 10},
    ):
        res = client.post("/fan-voice/opinion-review/generate", json={"context_type": "home", "context_id": "today"})
    assert res.status_code == 200
    assert res.json()["review_id"] == 10
