"""Unit tests for services/report_repository.py."""
from datetime import date
from unittest.mock import MagicMock, patch

from services import report_repository


_UNSET = object()


def _make_chain(*, data=None, single_data=_UNSET):
    """Build a MagicMock supabase query chain.

    Pass single_data=None to simulate maybe_single() returning no row (result.data is None).
    Omit single_data (default) to use list data.
    """
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.in_.return_value = mock
    mock.gte.return_value = mock
    mock.lte.return_value = mock
    mock.maybe_single.return_value = mock
    mock.upsert.return_value = mock
    if single_data is not _UNSET:
        mock.execute.return_value = MagicMock(data=single_data)
    else:
        mock.execute.return_value = MagicMock(data=data if data is not None else [])
    return mock


def _mock_db(chain):
    db = MagicMock()
    db.table.return_value = chain
    return db


class TestListReports:
    def test_returns_data(self):
        chain = _make_chain(data=[{"id": 1}])
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.list_reports("team_daily_report", limit=10)
        assert result == [{"id": 1}]

    def test_applies_player_filter(self):
        chain = _make_chain(data=[])
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            report_repository.list_reports("player_daily_report", limit=5, player_id=42)
        chain.eq.assert_called_with("player_id", 42)

    def test_no_player_filter_by_default(self):
        chain = _make_chain(data=[])
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            report_repository.list_reports("team_daily_report", limit=5)
        for call in chain.eq.call_args_list:
            assert call[0][0] != "player_id"


class TestGetReport:
    def test_returns_data(self):
        chain = _make_chain(single_data={"id": 5, "date": "2026-05-22"})
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.get_report("team_daily_report", date(2026, 5, 22))
        assert result == {"id": 5, "date": "2026-05-22"}

    def test_returns_none_when_missing(self):
        chain = _make_chain(single_data=None)
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.get_report("team_daily_report", date(2026, 5, 22))
        assert result is None

    def test_filters_by_player_id(self):
        chain = _make_chain(single_data=None)
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            report_repository.get_report("player_daily_report", date(2026, 5, 22), player_id=7)
        eq_calls = [c[0] for c in chain.eq.call_args_list]
        assert ("player_id", 7) in eq_calls


class TestReportExists:
    def test_true_when_data_present(self):
        chain = _make_chain(single_data={"id": 1})
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.report_exists("team_daily_report", date(2026, 5, 22))
        assert result is True

    def test_false_when_no_data(self):
        chain = _make_chain(single_data=None)
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.report_exists("team_daily_report", date(2026, 5, 22))
        assert result is False


class TestFetchPlayerMentions:
    def test_empty_ids_returns_early_without_db_call(self):
        db = MagicMock()
        with patch.object(report_repository, "supabase", db):
            result = report_repository.fetch_player_mentions(article_ids=[])
        assert result == []
        db.table.assert_not_called()

    def test_returns_data(self):
        data = [{"player_id": 1, "players": {"name": "홍길동"}}]
        chain = _make_chain(data=data)
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.fetch_player_mentions([10, 20])
        assert result == data


class TestFetchArticlesForDay:
    def test_queries_published_at_range(self):
        chain = _make_chain(data=[])
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            report_repository.fetch_articles_for_day(date(2026, 5, 22))
        assert chain.gte.called
        assert chain.lte.called

    def test_returns_articles(self):
        data = [{"id": 1, "title": "Test"}]
        chain = _make_chain(data=data)
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.fetch_articles_for_day(date(2026, 5, 22))
        assert result == data


class TestFetchPlayerMentionsWithPosition:
    def test_empty_ids_skips_db(self):
        db = MagicMock()
        with patch.object(report_repository, "supabase", db):
            result = report_repository.fetch_player_mentions_with_position([])
        assert result == []
        db.table.assert_not_called()


class TestFetchGameForDay:
    def test_fetch_games_for_day_returns_all_rows(self):
        data = [
            {"date": "2026-05-22", "game_seq": 1, "opponent": "A"},
            {"date": "2026-05-22", "game_seq": 2, "opponent": "B"},
        ]
        chain = _make_chain(data=data)
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.fetch_games_for_day(date(2026, 5, 22))
        assert result == data

    def test_fetch_games_for_day_returns_empty(self):
        chain = _make_chain(data=[])
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.fetch_games_for_day(date(2026, 5, 22))
        assert result == []

    def test_returns_first_row_when_exists(self):
        data = [{"date": "2026-05-22", "opponent": "A"}, {"date": "2026-05-22", "opponent": "B"}]
        chain = _make_chain(data=data)
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.fetch_game_for_day(date(2026, 5, 22))
        assert result == data[0]

    def test_returns_none_when_empty(self):
        chain = _make_chain(data=[])
        with patch.object(report_repository, "supabase", _mock_db(chain)):
            result = report_repository.fetch_game_for_day(date(2026, 5, 22))
        assert result is None
