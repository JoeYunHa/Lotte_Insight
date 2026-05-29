"""Unit tests for player_repository caching logic."""

from datetime import date
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player_row(player_id=1, name="전준우", position="OF", status="active"):
    return {"id": player_id, "name": name, "position": position, "status": status,
            "name_variants": [name]}


def _make_supabase_for_list(rows):
    mock_db = MagicMock()
    t = MagicMock()
    t.select.return_value.order.return_value.execute.return_value.data = rows
    t.select.return_value.eq.return_value.order.return_value.execute.return_value.data = rows
    mock_db.table.return_value = t
    return mock_db


def _make_supabase_for_detail(player_row, stats_rows=None):
    stats_rows = stats_rows or []
    mock_db = MagicMock()

    players_table = MagicMock()
    players_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = player_row

    stats_table = MagicMock()
    stats_q = MagicMock()
    stats_q.execute.return_value.data = stats_rows
    stats_q.eq.return_value = stats_q
    stats_q.order.return_value.limit.return_value = stats_q
    stats_table.select.return_value.eq.return_value = stats_q

    def table_side_effect(name):
        return players_table if name == "players" else stats_table

    mock_db.table.side_effect = table_side_effect
    return mock_db


def _mock_settings(history_limit=30):
    m = MagicMock()
    m.player_stats_history_limit = history_limit
    return m


def _mock_cache(hit_value=None):
    m = MagicMock()
    m.get_json.return_value = hit_value
    m.ttl_seconds.return_value = 3600
    return m


# ---------------------------------------------------------------------------
# list_players
# ---------------------------------------------------------------------------

class TestListPlayersCaching:
    def test_cache_hit_returns_cached_value(self):
        from services import player_repository

        cached = [{"id": 1, "name": "전준우"}]
        mc = _mock_cache(hit_value=cached)
        mock_db = MagicMock()

        with patch("services.player_repository.cache", mc), \
             patch.object(player_repository, "supabase", mock_db):
            result = player_repository.list_players()

        assert result == cached
        mock_db.table.assert_not_called()
        mc.set_json.assert_not_called()

    def test_cache_miss_queries_db(self):
        from services import player_repository

        rows = [_make_player_row()]
        mc = _mock_cache()
        mock_db = _make_supabase_for_list(rows)

        with patch("services.player_repository.cache", mc), \
             patch.object(player_repository, "supabase", mock_db):
            result = player_repository.list_players()

        assert result == rows

    def test_cache_miss_writes_result(self):
        from services import player_repository

        rows = [_make_player_row()]
        mc = _mock_cache()
        mock_db = _make_supabase_for_list(rows)

        with patch("services.player_repository.cache", mc), \
             patch.object(player_repository, "supabase", mock_db):
            player_repository.list_players()

        mc.set_json.assert_called_once()
        key, value, ttl = mc.set_json.call_args[0]
        assert key == "player:list:all"
        assert value == rows
        assert ttl == 7200  # _PLAYER_LIST_TTL

    def test_cache_key_includes_status(self):
        from services import player_repository

        mc = _mock_cache()
        mock_db = _make_supabase_for_list([])

        with patch("services.player_repository.cache", mc), \
             patch.object(player_repository, "supabase", mock_db):
            player_repository.list_players(status="active")

        key = mc.get_json.call_args[0][0]
        assert key == "player:list:active"

    def test_cache_key_none_status_is_all(self):
        from services import player_repository

        mc = _mock_cache()
        mock_db = _make_supabase_for_list([])

        with patch("services.player_repository.cache", mc), \
             patch.object(player_repository, "supabase", mock_db):
            player_repository.list_players(status=None)

        key = mc.get_json.call_args[0][0]
        assert key == "player:list:all"


# ---------------------------------------------------------------------------
# get_player
# ---------------------------------------------------------------------------

class TestGetPlayerCaching:
    def test_cache_hit_returns_cached_value(self):
        from services import player_repository

        cached = {"id": 1, "name": "전준우", "stats": []}
        mc = _mock_cache(hit_value=cached)
        mock_db = MagicMock()

        with patch("services.player_repository.cache", mc), \
             patch.object(player_repository, "supabase", mock_db):
            result = player_repository.get_player(1)

        assert result == cached
        mock_db.table.assert_not_called()

    def test_cache_miss_returns_player_with_stats(self):
        from services import player_repository

        player_row = _make_player_row()
        stats = [{"date": "2026-05-28", "avg": 0.310}]
        mc = _mock_cache()
        mock_db = _make_supabase_for_detail(player_row, stats)

        with patch("services.player_repository.cache", mc), \
             patch("services.player_repository.today_kst", return_value=date(2026, 5, 29)), \
             patch("services.player_repository.settings", _mock_settings()), \
             patch.object(player_repository, "supabase", mock_db):
            result = player_repository.get_player(1)

        assert result is not None
        assert result["id"] == 1
        assert result["stats"] == stats

    def test_cache_miss_writes_result(self):
        from services import player_repository

        player_row = _make_player_row()
        mc = _mock_cache()
        mock_db = _make_supabase_for_detail(player_row)

        with patch("services.player_repository.cache", mc), \
             patch("services.player_repository.today_kst", return_value=date(2026, 5, 29)), \
             patch("services.player_repository.settings", _mock_settings()), \
             patch.object(player_repository, "supabase", mock_db):
            result = player_repository.get_player(1)

        mc.set_json.assert_called_once()
        key, value, ttl = mc.set_json.call_args[0]
        assert key == "player:1:stats:latest"
        assert value == result
        assert ttl == 3600

    def test_returns_none_for_missing_player(self):
        from services import player_repository

        mc = _mock_cache()
        mock_db = _make_supabase_for_detail(player_row=None)

        with patch("services.player_repository.cache", mc), \
             patch.object(player_repository, "supabase", mock_db):
            result = player_repository.get_player(999)

        assert result is None
        mc.set_json.assert_not_called()

    def test_cache_key_with_stats_date(self):
        from services import player_repository

        mc = _mock_cache()
        mock_db = _make_supabase_for_detail(_make_player_row())

        with patch("services.player_repository.cache", mc), \
             patch("services.player_repository.today_kst", return_value=date(2026, 5, 29)), \
             patch.object(player_repository, "supabase", mock_db):
            player_repository.get_player(1, stats_date=date(2026, 5, 28))

        key = mc.get_json.call_args[0][0]
        assert key == "player:1:stats:2026-05-28"

    def test_cache_key_without_stats_date_is_latest(self):
        from services import player_repository

        mc = _mock_cache()
        mock_db = _make_supabase_for_detail(_make_player_row())

        with patch("services.player_repository.cache", mc), \
             patch("services.player_repository.today_kst", return_value=date(2026, 5, 29)), \
             patch("services.player_repository.settings", _mock_settings()), \
             patch.object(player_repository, "supabase", mock_db):
            player_repository.get_player(5)

        key = mc.get_json.call_args[0][0]
        assert key == "player:5:stats:latest"
