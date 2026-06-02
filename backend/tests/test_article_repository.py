"""Unit tests for services/article_repository.py."""

import json
import logging
from unittest.mock import MagicMock, patch


def _make_raw(
    *,
    labels=None,
    event_summary=None,
    extra=None,
) -> dict:
    raw = {
        "id": 1,
        "source_url": "http://example.com",
        "title": "Test Article",
        "published_at": "2026-05-22T10:00:00+09:00",
        "article_labels": labels or [],
        "event_summary": event_summary,
        "article_players": [],
    }
    if extra:
        raw.update(extra)
    return raw


class TestReshapeArticle:
    def test_no_labels(self):
        from services.article_repository import _reshape_article

        result = _reshape_article(_make_raw())
        assert result["primary_label"] is None
        assert result["confidence"] is None
        assert "article_labels" not in result

    def test_picks_highest_confidence_label(self):
        from services.article_repository import _reshape_article

        raw = _make_raw(labels=[
            {"label": "ETC", "confidence": 0.2},
            {"label": "MATCH_RELATED", "confidence": 0.85},
        ])
        result = _reshape_article(raw)
        assert result["primary_label"] == "MATCH_RELATED"
        assert result["confidence"] == 0.85

    def test_event_summary_json_parsed(self):
        from services.article_repository import _reshape_article

        payload = {
            "event_summary": "롯데 승리",
            "lotte_stance": "positive",
            "key_players": ["전준우"],
        }
        raw = _make_raw(event_summary=json.dumps(payload, ensure_ascii=False))
        result = _reshape_article(raw)
        assert result["event_summary"] == "롯데 승리"
        assert result["lotte_stance"] == "positive"
        assert result["key_players"] == ["전준우"]

    def test_invalid_event_summary_json(self):
        from services.article_repository import _reshape_article

        raw = _make_raw(event_summary="not-json")
        result = _reshape_article(raw)
        assert result["event_summary"] is None
        assert result["lotte_stance"] is None
        assert result["key_players"] == []


class TestListArticlesServerSideFilter:
    """list_articles now uses !inner JOIN for server-side filtering."""

    def _mock_chain(self, data):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.lte.return_value = chain
        chain.order.return_value = chain
        chain.range.return_value = chain
        chain.execute.return_value = MagicMock(data=data)
        return chain

    def test_label_filter_uses_inner_join(self):
        from services import article_repository

        chain = self._mock_chain([])
        mock_db = MagicMock()
        mock_db.table.return_value = chain

        with patch.object(article_repository, "supabase", mock_db):
            article_repository.list_articles(label="MATCH_RELATED")

        select_call = chain.select.call_args[0][0]
        assert "article_labels!inner" in select_call
        # eq was called with the label filter
        eq_calls = [str(c) for c in chain.eq.call_args_list]
        assert any("article_labels.label" in str(c) for c in chain.eq.call_args_list)

    def test_player_filter_uses_inner_join(self):
        from services import article_repository

        chain = self._mock_chain([])
        mock_db = MagicMock()
        mock_db.table.return_value = chain

        with patch.object(article_repository, "supabase", mock_db):
            article_repository.list_articles(player_id=42)

        select_call = chain.select.call_args[0][0]
        assert "article_players!inner" in select_call
        assert any("article_players.player_id" in str(c) for c in chain.eq.call_args_list)

    def test_no_filter_uses_left_join(self):
        from services import article_repository

        chain = self._mock_chain([])
        mock_db = MagicMock()
        mock_db.table.return_value = chain

        with patch.object(article_repository, "supabase", mock_db):
            article_repository.list_articles()

        select_call = chain.select.call_args[0][0]
        assert "article_labels!inner" not in select_call
        assert "article_players!inner" not in select_call

    def test_returns_empty_list_when_no_data(self):
        from services import article_repository

        chain = self._mock_chain(None)  # SDK returns None
        mock_db = MagicMock()
        mock_db.table.return_value = chain

        with patch.object(article_repository, "supabase", mock_db):
            result = article_repository.list_articles()

        assert result == []
