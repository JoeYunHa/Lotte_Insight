"""Unit tests for services/topic_repository.py."""

from datetime import date
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cluster(
    *,
    id="2026-05-22_c01",
    map_date="2026-05-22",
    article_count=5,
    representative_article_id=None,
    title="클러스터 제목",
    summary="요약 문장",
    label_hint="MATCH_RELATED",
    key_players=None,
    created_at="2026-05-22T01:00:00+00:00",
    updated_at="2026-05-22T01:00:00+00:00",
) -> dict:
    return {
        "id": id,
        "map_date": map_date,
        "article_count": article_count,
        "representative_article_id": representative_article_id,
        "title": title,
        "summary": summary,
        "label_hint": label_hint,
        "key_players": key_players or ["전준우"],
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _point(
    *,
    article_id="aaaa-bbbb",
    cluster_id="2026-05-22_c01",
    cluster_rank=1,
    x=1.0,
    y=2.0,
    is_outlier=False,
    article=None,
) -> dict:
    return {
        "article_id": article_id,
        "cluster_id": cluster_id,
        "cluster_rank": cluster_rank,
        "x": x,
        "y": y,
        "is_outlier": is_outlier,
        "articles": article,
    }


def _article_row(
    *,
    id="aaaa-bbbb",
    title="롯데 승리",
    source_name="news.com",
    published_at="2026-05-22T09:00:00+09:00",
    labels=None,
) -> dict:
    return {
        "id": id,
        "title": title,
        "source_name": source_name,
        "published_at": published_at,
        "article_labels": labels if labels is not None else [{"label": "MATCH_RELATED", "confidence": 0.9}],
    }


def _make_supabase(clusters_data, points_data):
    """Build a mock supabase client returning given data per table."""
    mock_db = MagicMock()

    def table_side_effect(table_name: str):
        t = MagicMock()
        if table_name == "topic_clusters":
            t.select.return_value.eq.return_value.order.return_value.execute.return_value.data = clusters_data
        else:
            # article_topic_points: .select().eq().order(cluster_rank).execute()
            t.select.return_value.eq.return_value.order.return_value.execute.return_value.data = points_data
        return t

    mock_db.table.side_effect = table_side_effect
    return mock_db


# ---------------------------------------------------------------------------
# _reshape_clusters
# ---------------------------------------------------------------------------

class TestReshapeClusters:
    def test_basic_shape(self):
        from services.topic_repository import _reshape_clusters

        result = _reshape_clusters([_cluster()])
        assert len(result) == 1
        c = result[0]
        assert c["id"] == "2026-05-22_c01"
        assert c["article_count"] == 5
        assert c["title"] == "클러스터 제목"
        assert c["label_hint"] == "MATCH_RELATED"
        assert c["key_players"] == ["전준우"]

    def test_representative_article_id_none(self):
        from services.topic_repository import _reshape_clusters

        result = _reshape_clusters([_cluster(representative_article_id=None)])
        assert result[0]["representative_article_id"] is None

    def test_representative_article_id_stringified(self):
        from services.topic_repository import _reshape_clusters

        uid = "cccc-dddd-eeee"
        result = _reshape_clusters([_cluster(representative_article_id=uid)])
        assert result[0]["representative_article_id"] == uid

    def test_none_title_becomes_empty_string(self):
        from services.topic_repository import _reshape_clusters

        c = _cluster()
        c["title"] = None
        result = _reshape_clusters([c])
        assert result[0]["title"] == ""

    def test_none_key_players_becomes_empty_list(self):
        from services.topic_repository import _reshape_clusters

        c = _cluster()
        c["key_players"] = None
        result = _reshape_clusters([c])
        assert result[0]["key_players"] == []

    def test_multiple_clusters_preserved(self):
        from services.topic_repository import _reshape_clusters

        clusters = [
            _cluster(id="2026-05-22_c01", article_count=10),
            _cluster(id="2026-05-22_c02", article_count=3),
        ]
        result = _reshape_clusters(clusters)
        assert len(result) == 2
        assert result[0]["id"] == "2026-05-22_c01"


# ---------------------------------------------------------------------------
# _reshape_points
# ---------------------------------------------------------------------------

class TestReshapePoints:
    def test_basic_shape(self):
        from services.topic_repository import _reshape_points

        row = _point(article=_article_row())
        result = _reshape_points([row])
        assert len(result) == 1
        p = result[0]
        assert p["article_id"] == "aaaa-bbbb"
        assert p["cluster_id"] == "2026-05-22_c01"
        assert p["x"] == 1.0
        assert p["y"] == 2.0
        assert p["is_outlier"] is False

    def test_article_primary_label_resolved(self):
        from services.topic_repository import _reshape_points

        labels = [
            {"label": "ETC", "confidence": 0.3},
            {"label": "MATCH_RELATED", "confidence": 0.85},
        ]
        row = _point(article=_article_row(labels=labels))
        result = _reshape_points([row])
        assert result[0]["article"]["primary_label"] == "MATCH_RELATED"

    def test_article_id_stringified(self):
        from services.topic_repository import _reshape_points

        row = _point(article_id="uuid-string-123")
        result = _reshape_points([row])
        assert result[0]["article_id"] == "uuid-string-123"

    def test_no_article_row_yields_none(self):
        from services.topic_repository import _reshape_points

        row = _point(article=None)
        result = _reshape_points([row])
        assert result[0]["article"] is None

    def test_outlier_flag_preserved(self):
        from services.topic_repository import _reshape_points

        row = _point(is_outlier=True, cluster_id=None)
        result = _reshape_points([row])
        assert result[0]["is_outlier"] is True

    def test_empty_article_labels_gives_no_primary_label(self):
        from services.topic_repository import _reshape_points

        row = _point(article=_article_row(labels=[]))
        result = _reshape_points([row])
        assert result[0]["article"]["primary_label"] is None

    def test_coordinates_cast_to_float(self):
        from services.topic_repository import _reshape_points

        row = _point(x=1, y=2)  # int from DB
        result = _reshape_points([row])
        assert isinstance(result[0]["x"], float)
        assert isinstance(result[0]["y"], float)


# ---------------------------------------------------------------------------
# get_topic_map
# ---------------------------------------------------------------------------

class TestGetTopicMap:
    def test_returns_none_when_no_clusters(self):
        from services import topic_repository

        mock_db = _make_supabase(clusters_data=[], points_data=[])
        with patch.object(topic_repository, "supabase", mock_db):
            result = topic_repository.get_topic_map(date(2026, 5, 22))
        assert result is None

    def test_returns_map_date(self):
        from services import topic_repository

        mock_db = _make_supabase(
            clusters_data=[_cluster()],
            points_data=[_point(article=_article_row())],
        )
        with patch.object(topic_repository, "supabase", mock_db):
            result = topic_repository.get_topic_map(date(2026, 5, 22))
        assert result is not None
        assert result["map_date"] == "2026-05-22"

    def test_clusters_sorted_by_article_count_desc(self):
        from services import topic_repository

        # DB mock returns already in desc order (query uses .order)
        mock_db = _make_supabase(
            clusters_data=[
                _cluster(id="2026-05-22_c01", article_count=10),
                _cluster(id="2026-05-22_c02", article_count=3),
            ],
            points_data=[],
        )
        with patch.object(topic_repository, "supabase", mock_db):
            result = topic_repository.get_topic_map(date(2026, 5, 22))
        assert result["clusters"][0]["article_count"] == 10

    def test_points_list_populated(self):
        from services import topic_repository

        mock_db = _make_supabase(
            clusters_data=[_cluster()],
            points_data=[_point(article=_article_row()), _point(article_id="zzzz", article=None)],
        )
        with patch.object(topic_repository, "supabase", mock_db):
            result = topic_repository.get_topic_map(date(2026, 5, 22))
        assert len(result["points"]) == 2

    def test_empty_points_allowed(self):
        from services import topic_repository

        mock_db = _make_supabase(clusters_data=[_cluster()], points_data=[])
        with patch.object(topic_repository, "supabase", mock_db):
            result = topic_repository.get_topic_map(date(2026, 5, 22))
        assert result is not None
        assert result["points"] == []

    def test_points_query_orders_by_cluster_rank_nulls_last(self):
        from services import topic_repository

        clusters_table = MagicMock()
        clusters_table.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [_cluster()]

        points_eq = MagicMock()
        points_order = MagicMock()
        points_order.execute.return_value.data = []
        points_eq.order.return_value = points_order

        points_table = MagicMock()
        points_table.select.return_value.eq.return_value = points_eq

        mock_db = MagicMock()
        mock_db.table.side_effect = lambda name: clusters_table if name == "topic_clusters" else points_table

        with patch.object(topic_repository, "supabase", mock_db):
            topic_repository.get_topic_map(date(2026, 5, 22))

        points_eq.order.assert_called_once_with("cluster_rank", nullsfirst=False)

    def test_unknown_label_passes_through_unchanged(self):
        from services import topic_repository

        row = _point(article=_article_row(labels=[{"label": "UNKNOWN_LABEL", "confidence": 0.9}]))
        mock_db = _make_supabase(clusters_data=[_cluster()], points_data=[row])
        with patch.object(topic_repository, "supabase", mock_db):
            result = topic_repository.get_topic_map(date(2026, 5, 22))
        # Repository does not validate labels — passes through as-is
        assert result["points"][0]["article"]["primary_label"] == "UNKNOWN_LABEL"

    def test_queries_correct_date(self):
        from services import topic_repository

        mock_db = _make_supabase(clusters_data=[_cluster()], points_data=[])
        with patch.object(topic_repository, "supabase", mock_db):
            topic_repository.get_topic_map(date(2026, 5, 22))

        calls = mock_db.table.call_args_list
        table_names = [c.args[0] for c in calls]
        assert "topic_clusters" in table_names
        assert "article_topic_points" in table_names
