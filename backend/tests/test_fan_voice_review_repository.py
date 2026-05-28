from datetime import date
from unittest.mock import MagicMock, patch

from services import fan_voice_review_repository


def _chain(data=None):
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.lte.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.upsert.return_value = mock
    mock.delete.return_value = mock
    mock.insert.return_value = mock
    mock.execute.return_value = MagicMock(data=data if data is not None else [])
    return mock


def test_latest_game_date_returns_none_when_empty():
    chain = _chain(data=[])
    db = MagicMock()
    db.table.return_value = chain
    with patch.object(fan_voice_review_repository, "supabase", db):
        assert fan_voice_review_repository.latest_game_date(date(2026, 5, 28)) is None


def test_latest_game_date_parses_date():
    chain = _chain(data=[{"date": "2026-05-27"}])
    db = MagicMock()
    db.table.return_value = chain
    with patch.object(fan_voice_review_repository, "supabase", db):
        assert fan_voice_review_repository.latest_game_date(date(2026, 5, 28)) == date(2026, 5, 27)


def test_upsert_daily_review_raises_on_empty_result():
    """Test that upsert_daily_review raises RuntimeError when result.data is empty."""
    chain = _chain(data=[])  # Empty result
    db = MagicMock()
    db.table.return_value = chain

    with patch.object(fan_voice_review_repository, "supabase", db):
        try:
            fan_voice_review_repository.upsert_daily_review(
                {"game_date": "2026-05-28", "context_key": "home:today"}
            )
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Failed to upsert review" in str(e)
            assert "2026-05-28" in str(e)


def test_upsert_daily_review_returns_first_row():
    """Test that upsert_daily_review returns the first row when successful."""
    chain = _chain(data=[{"id": 123, "game_date": "2026-05-28"}])
    db = MagicMock()
    db.table.return_value = chain

    with patch.object(fan_voice_review_repository, "supabase", db):
        result = fan_voice_review_repository.upsert_daily_review(
            {"game_date": "2026-05-28", "context_key": "home:today"}
        )
        assert result["id"] == 123
        assert result["game_date"] == "2026-05-28"


def test_replace_daily_opinions_calls_rpc():
    """Test that replace_daily_opinions uses RPC for transaction safety."""
    chain = _chain(data=[])
    db = MagicMock()
    db.rpc.return_value = chain

    with patch.object(fan_voice_review_repository, "supabase", db):
        fan_voice_review_repository.replace_daily_opinions(
            review_id=5,
            opinions=[
                {
                    "cluster_key": "c1",
                    "opinion_title": "Test Opinion",
                    "representative_message": "Test message",
                    "mention_count": 10,
                    "reaction_sum": 5,
                    "score": 8.5,
                    "sentiment_hint": "positive",
                    "primary_player_id": 123,
                    "evidence_message_ids": ["uuid1", "uuid2"],
                    "evidence_count": 2,
                }
            ],
        )

    # Verify RPC was called with correct function name and parameters
    db.rpc.assert_called_once()
    call_args, call_kwargs = db.rpc.call_args
    assert call_args[0] == "replace_daily_opinions"
    assert call_args[1]["p_review_id"] == 5
    assert len(call_args[1]["p_opinions"]) == 1

    # Verify opinions data structure
    opinion = call_args[1]["p_opinions"][0]
    assert opinion["cluster_key"] == "c1"
    assert opinion["mention_count"] == 10
    assert opinion["evidence_count"] == 2
