"""Unit tests for services/article_repository.py."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest


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


class TestArticleIdsForRelationTruncation:
    def test_warning_logged_when_limit_hit(self, caplog):
        from services import article_repository

        limit = article_repository._RELATION_ID_LIMIT
        fake_data = [{"article_id": i} for i in range(limit)]

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=fake_data)
        mock_chain.eq.return_value = mock_chain
        mock_chain.select.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain

        with patch.object(article_repository.supabase, "table", return_value=mock_chain):
            with caplog.at_level(logging.WARNING, logger="services.article_repository"):
                result = article_repository._article_ids_for_relation(
                    "article_labels", "label", "MATCH_RELATED"
                )

        assert len(result) == limit
        assert any("incomplete" in msg.lower() or str(limit) in msg for msg in caplog.messages)

    def test_no_warning_when_under_limit(self, caplog):
        from services import article_repository

        fake_data = [{"article_id": i} for i in range(5)]

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=fake_data)
        mock_chain.eq.return_value = mock_chain
        mock_chain.select.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain

        with patch.object(article_repository.supabase, "table", return_value=mock_chain):
            with caplog.at_level(logging.WARNING, logger="services.article_repository"):
                article_repository._article_ids_for_relation(
                    "article_labels", "label", "MATCH_RELATED"
                )

        assert not caplog.records
