"""Integration-style unit tests for FastAPI route handlers."""
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestArticlesApi:
    def test_list_articles_ok(self, client):
        with patch("api.articles.list_article_records", return_value=[]):
            response = client.get("/articles/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_articles_with_label_filter(self, client):
        with patch("api.articles.list_article_records", return_value=[]) as mock_list:
            client.get("/articles/?label=MATCH_RELATED")
        mock_list.assert_called_once()
        kwargs = mock_list.call_args[1]
        assert kwargs["label"] == "MATCH_RELATED"

    def test_get_article_found(self, client):
        article = {"id": 1, "title": "롯데 승리"}
        with patch("api.articles.get_article_record", return_value=article):
            response = client.get("/articles/1")
        assert response.status_code == 200
        assert response.json()["id"] == 1

    def test_get_article_not_found(self, client):
        with patch("api.articles.get_article_record", return_value=None):
            response = client.get("/articles/999")
        assert response.status_code == 404

    def test_list_articles_limit_validation(self, client):
        with patch("api.articles.list_article_records", return_value=[]):
            response = client.get("/articles/?limit=0")
        assert response.status_code == 422

    def test_list_articles_offset_negative_rejected(self, client):
        with patch("api.articles.list_article_records", return_value=[]):
            response = client.get("/articles/?offset=-1")
        assert response.status_code == 422


class TestReportsApi:
    def test_list_team_reports_ok(self, client):
        with patch("services.report_service.list_team_reports", return_value=[]):
            response = client.get("/reports/team")
        assert response.status_code == 200

    def test_get_team_report_not_found(self, client):
        with patch("services.report_service.get_team_report", return_value=None):
            response = client.get("/reports/team/2026-05-22")
        assert response.status_code == 404

    def test_get_team_report_found(self, client):
        report = {"date": "2026-05-22", "issue_summary": "요약"}
        with patch("services.report_service.get_team_report", return_value=report):
            response = client.get("/reports/team/2026-05-22")
        assert response.status_code == 200

    def test_get_player_report_not_found(self, client):
        with patch("services.report_service.get_player_report", return_value=None):
            response = client.get("/reports/players/1/2026-05-22")
        assert response.status_code == 404


class TestPlayersApi:
    def test_list_players_ok(self, client):
        with patch("api.players.list_player_records", return_value=[]):
            response = client.get("/players/")
        assert response.status_code == 200

    def test_get_player_not_found(self, client):
        with patch("api.players.get_player_record", return_value=None):
            response = client.get("/players/999")
        assert response.status_code == 404

    def test_get_player_found(self, client):
        player = {"id": 1, "name": "전준우"}
        with patch("api.players.get_player_record", return_value=player):
            response = client.get("/players/1")
        assert response.status_code == 200
        assert response.json()["name"] == "전준우"


class TestHomeApi:
    def test_get_home_report_ok(self, client):
        home_data = {
            "date": "2026-05-22",
            "article_count": 0,
            "label_counts": {},
            "sentiment": {"positive": 0, "negative": 0, "neutral": 0, "analyzed": 0},
            "lead_label": None,
            "lead_summary": None,
            "lead_key_players": [],
            "top_players": [],
            "team_report": None,
            "game_context": None,
        }
        with (
            patch("api.home.cache") as mock_cache,
            patch("api.home.home_service.build_home_report", return_value=home_data),
        ):
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 3600
            response = client.get("/reports/home?report_date=2026-05-22")
        assert response.status_code == 200
        assert response.json()["date"] == "2026-05-22"

    def test_get_home_report_cached(self, client):
        cached = {"date": "2026-05-22", "cached": True}
        with patch("api.home.cache") as mock_cache:
            mock_cache.get_json.return_value = cached
            response = client.get("/reports/home?report_date=2026-05-22")
        assert response.status_code == 200
        assert response.json()["cached"] is True
