from datetime import date
from unittest.mock import MagicMock, patch

from batch import game_collector


class TestSyncGame:
    def test_returns_none_when_no_game(self):
        with patch.object(game_collector, "fetch_month_games", return_value=[]):
            assert game_collector.sync_game(date(2026, 5, 22)) is None

    def test_upserts_single_game_with_seq_1(self):
        games = [
            {
                "date": "2026-05-22",
                "opponent": "A",
                "venue": "사직",
                "home_away": "home",
                "game_time": "18:30",
                "score": None,
                "result": None,
            }
        ]
        mock_chain = MagicMock()
        mock_chain.upsert.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock()
        mock_supabase = MagicMock()
        mock_supabase.table.return_value = mock_chain
        with (
            patch.object(game_collector, "fetch_month_games", return_value=games),
            patch.object(game_collector, "supabase", mock_supabase),
        ):
            result = game_collector.sync_game(date(2026, 5, 22))

        assert result is not None
        rows = mock_chain.upsert.call_args[0][0]
        assert len(rows) == 1
        assert rows[0]["game_seq"] == 1
        assert mock_chain.upsert.call_args[1]["on_conflict"] == "date,game_seq"

    def test_upserts_doubleheader_with_separate_sequences(self):
        games = [
            {
                "date": "2026-05-22",
                "opponent": "A",
                "venue": "사직",
                "home_away": "home",
                "game_time": "14:00",
                "score": "3-1",
                "result": "승",
            },
            {
                "date": "2026-05-22",
                "opponent": "A",
                "venue": "사직",
                "home_away": "home",
                "game_time": "18:30",
                "score": None,
                "result": None,
            },
        ]
        mock_chain = MagicMock()
        mock_chain.upsert.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock()
        mock_supabase = MagicMock()
        mock_supabase.table.return_value = mock_chain
        with (
            patch.object(game_collector, "fetch_month_games", return_value=games),
            patch.object(game_collector, "supabase", mock_supabase),
        ):
            game_collector.sync_game(date(2026, 5, 22))

        rows = mock_chain.upsert.call_args[0][0]
        assert len(rows) == 2
        assert [row["game_seq"] for row in rows] == [1, 2]
