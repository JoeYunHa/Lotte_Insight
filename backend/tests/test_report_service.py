"""Unit tests for services/report_service.py."""
from datetime import date
from unittest.mock import MagicMock, patch

from services import report_service


class TestLoadCachedReport:
    def test_returns_cached_value_on_hit(self):
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = {"id": 1}
            result = report_service._load_cached_report("key", date.today(), lambda: None)
        assert result == {"id": 1}

    def test_returns_none_for_empty_sentinel(self):
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = report_service._CACHE_EMPTY
            result = report_service._load_cached_report("key", date.today(), lambda: None)
        assert result is None

    def test_calls_loader_on_cache_miss(self):
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 60
            result = report_service._load_cached_report("key", date.today(), lambda: {"fresh": True})
        assert result == {"fresh": True}

    def test_stores_empty_sentinel_when_loader_returns_none(self):
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 60
            report_service._load_cached_report("key", date.today(), lambda: None)
        args = mock_cache.set_json.call_args[0]
        assert args[1] == report_service._CACHE_EMPTY

    def test_stores_data_when_loader_succeeds(self):
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 60
            report_service._load_cached_report("key", date.today(), lambda: {"x": 1})
        args = mock_cache.set_json.call_args[0]
        assert args[1] == {"x": 1}


class TestListTeamReports:
    def test_delegates_to_repository(self):
        expected = [{"id": 1, "date": "2026-05-22"}]
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 60
            with patch.object(report_service.report_repository, "list_reports", return_value=expected):
                result = report_service.list_team_reports(5)
        assert result == expected

    def test_uses_correct_table(self):
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 60
            with patch.object(report_service.report_repository, "list_reports", return_value=[]) as mock_list:
                report_service.list_team_reports(10)
        mock_list.assert_called_once_with(report_service.TEAM_REPORT_TABLE, limit=10)


class TestGetTeamReport:
    def test_returns_cached(self):
        expected = {"id": 2}
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = expected
            result = report_service.get_team_report(date(2026, 5, 22))
        assert result == expected

    def test_cache_miss_queries_repository(self):
        expected = {"id": 3}
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 60
            with patch.object(report_service.report_repository, "get_report", return_value=expected):
                result = report_service.get_team_report(date(2026, 5, 22))
        assert result == expected


class TestListPlayerReports:
    def test_cache_key_includes_player_id(self):
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = []
            result = report_service.list_player_reports(player_id=7, limit=5)
        cache_key = mock_cache.get_json.call_args[0][0]
        assert "7" in cache_key

    def test_delegates_to_repository(self):
        expected = [{"id": 10}]
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 60
            with patch.object(report_service.report_repository, "list_reports", return_value=expected):
                result = report_service.list_player_reports(player_id=7, limit=5)
        assert result == expected


class TestGetPlayerReport:
    def test_returns_correct_report(self):
        expected = {"player_id": 7}
        with patch("services.report_service.cache") as mock_cache:
            mock_cache.get_json.return_value = None
            mock_cache.ttl_seconds.return_value = 60
            with patch.object(report_service.report_repository, "get_report", return_value=expected):
                result = report_service.get_player_report(player_id=7, report_date=date(2026, 5, 22))
        assert result == expected
