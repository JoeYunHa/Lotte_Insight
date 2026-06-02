"""
Unit tests for batch/news_collector.py — _save_labels_and_players and Step 5.

Focuses on:
  - NULL player_stance is excluded from upsert payload (no silent overwrite)
  - Valid player_stance is included in upsert payload
  - Non-lotte articles are skipped entirely
  - extract_players is no longer imported (alias_index used directly)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _make_item(url: str = "http://example.com/1") -> MagicMock:
    item = MagicMock()
    item.link = url
    return item


def _run_save(enriched: list[dict], id_map: dict[str, int]) -> list[dict]:
    """Run _save_labels_and_players and return the player_rows passed to upsert."""
    from batch import news_collector

    captured: list[list[dict]] = []

    def fake_table(name: str):
        mock = MagicMock()
        if name == "article_players":
            def capture_upsert(rows, **_kw):
                captured.append(rows)
                return MagicMock(data=[])
            mock.upsert.side_effect = capture_upsert
        else:
            mock.upsert.return_value = MagicMock(data=[])
        return mock

    mock_supabase = MagicMock()
    mock_supabase.table.side_effect = fake_table

    with patch.object(news_collector, "supabase", mock_supabase):
        news_collector._save_labels_and_players(enriched, id_map)

    return captured[0] if captured else []


class TestSaveLabelsAndPlayers:
    def test_null_stance_excluded_from_payload(self):
        """When stance label is None (model_error), player_stance must not be in upsert row."""
        enriched = [{
            "is_lotte_related": True,
            "normalized_url": "https://a.com/1",
            "item": _make_item("http://a.com/1"),
            "label_result": {"label": "MATCH_RELATED", "confidence": 0.9, "secondary_labels": []},
            "detected_player_ids": [42],
            "player_stances": {42: {"label": None, "confidence": 0.0, "source": "model_error"}},
        }]
        rows = _run_save(enriched, {"https://a.com/1": 100})
        assert len(rows) == 1
        assert "player_stance" not in rows[0]
        assert rows[0]["article_id"] == 100
        assert rows[0]["player_id"] == 42

    def test_valid_stance_included_in_payload(self):
        """When stance label is provided, player_stance must be in upsert row."""
        enriched = [{
            "is_lotte_related": True,
            "normalized_url": "https://a.com/2",
            "item": _make_item("http://a.com/2"),
            "label_result": {"label": "MATCH_RELATED", "confidence": 0.9, "secondary_labels": []},
            "detected_player_ids": [7],
            "player_stances": {7: {"label": "positive", "confidence": 0.82, "source": "koelectra"}},
        }]
        rows = _run_save(enriched, {"https://a.com/2": 200})
        assert len(rows) == 1
        assert rows[0]["player_stance"] == "positive"

    def test_not_applicable_stance_excluded(self):
        """not_applicable (model missing) also produces None label → key excluded."""
        enriched = [{
            "is_lotte_related": True,
            "normalized_url": "https://a.com/3",
            "item": _make_item("http://a.com/3"),
            "label_result": {"label": "ETC", "confidence": 0.5, "secondary_labels": []},
            "detected_player_ids": [5],
            "player_stances": {5: {"label": None, "confidence": 0.0, "source": "not_applicable"}},
        }]
        rows = _run_save(enriched, {"https://a.com/3": 300})
        assert "player_stance" not in rows[0]

    def test_non_lotte_articles_skipped(self):
        """Articles with is_lotte_related=False produce no player rows."""
        enriched = [{
            "is_lotte_related": False,
            "normalized_url": "http://a.com/4",
            "item": _make_item("http://a.com/4"),
            "label_result": {"label": "ETC", "confidence": 0.0, "secondary_labels": []},
            "detected_player_ids": [1],
            "player_stances": {1: {"label": "positive", "confidence": 0.9, "source": "koelectra"}},
        }]
        rows = _run_save(enriched, {"http://a.com/4": 400})
        assert rows == []

    def test_multiple_players_mixed_stances(self):
        """One player has a stance, another doesn't — only the valid one gets the key."""
        enriched = [{
            "is_lotte_related": True,
            "normalized_url": "https://a.com/5",
            "item": _make_item("http://a.com/5"),
            "label_result": {"label": "MATCH_RELATED", "confidence": 0.9, "secondary_labels": []},
            "detected_player_ids": [1, 2],
            "player_stances": {
                1: {"label": "negative", "confidence": 0.75, "source": "koelectra"},
                2: {"label": None, "confidence": 0.0, "source": "model_error"},
            },
        }]
        rows = _run_save(enriched, {"https://a.com/5": 500})
        by_player = {r["player_id"]: r for r in rows}
        assert by_player[1]["player_stance"] == "negative"
        assert "player_stance" not in by_player[2]


class TestExtractPlayersNotImported:
    def test_extract_players_removed_from_news_collector(self):
        """extract_players should no longer be imported by news_collector (alias_index used directly)."""
        import batch.news_collector as nc
        assert not hasattr(nc, "extract_players"), (
            "extract_players is still imported in news_collector — remove it and use alias_index directly"
        )

class TestNormalizedUrlPersistence:
    def test_save_uses_normalized_url_lookup(self):
        from batch import news_collector

        enriched = [{
            "is_lotte_related": True,
            "normalized_url": "https://a.com/1",
            "item": _make_item("http://www.a.com/1?utm=abc"),
            "label_result": {"label": "MATCH_RELATED", "confidence": 0.9, "secondary_labels": []},
            "detected_player_ids": [42],
            "player_stances": {42: {"label": "positive", "confidence": 0.9, "source": "koelectra"}},
        }]

        rows = _run_save(enriched, {"https://a.com/1": 100})
        assert len(rows) == 1
        assert rows[0]["article_id"] == 100

    def test_upsert_articles_writes_normalized_source_url(self):
        from batch import news_collector

        item = MagicMock()
        item.link = "http://www.example.com/article?id=1#top"
        item.source_name = "src"
        item.title = "title"
        item.published_at = "2026-05-26T00:00:00+00:00"

        enriched = [{
            "item": item,
            "normalized_url": "https://example.com/article",
            "event_summary_json": "{}",
            "collection_source": "naver_api",
        }]

        mock_chain = MagicMock()
        mock_chain.upsert.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(data=[{"id": 1}])
        mock_supabase = MagicMock()
        mock_supabase.table.return_value = mock_chain

        with patch.object(news_collector, "supabase", mock_supabase):
            news_collector._upsert_articles(enriched)

        rows = mock_chain.upsert.call_args[0][0]
        assert rows[0]["source_url"] == "https://example.com/article"
