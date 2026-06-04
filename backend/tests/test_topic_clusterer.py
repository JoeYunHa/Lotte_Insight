"""Unit tests for batch/topic_clusterer.py.

Tests cover pure-Python logic only (no torch, no DB).
Embedding, clustering, and projection are tested with prebuilt numpy arrays.
"""

import json
from collections import Counter
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from batch.topic_clusterer import (
    _MIN_ARTICLES,
    _MIN_CLUSTER_SIZE,
    _PROJECTION_MODEL_PCA,
    _PROJECTION_MODEL_UMAP,
    _build_clustering_text,
    _cluster_articles,
    _cosine_similarity_matrix,
    _derive_cluster_summary,
    _project_2d,
    _replace_topic_map,
    run_topic_clustering,
)


# ---------------------------------------------------------------------------
# _build_clustering_text
# ---------------------------------------------------------------------------

class TestBuildClusteringText:
    def _article(self, title="", event_summary=None, key_players=None, primary_label=None):
        blob = {}
        if event_summary is not None:
            blob["event_summary"] = event_summary
        if key_players is not None:
            blob["key_players"] = key_players
        return {
            "title": title,
            "event_summary": json.dumps(blob) if blob else None,
            "primary_label": primary_label,
        }

    def test_full_article(self):
        a = self._article(
            title="롯데 5연승",
            event_summary="롯데가 5연승을 달렸다",
            key_players=["박세웅", "전준우"],
            primary_label="MATCH_RELATED",
        )
        text = _build_clustering_text(a)
        assert "summary: 롯데가 5연승을 달렸다" in text
        assert "title: 롯데 5연승" in text
        assert "label: MATCH_RELATED" in text
        assert "players: 박세웅, 전준우" in text

    def test_missing_event_summary(self):
        a = self._article(title="롯데 부상 소식", primary_label="INJURY_ROSTER")
        text = _build_clustering_text(a)
        assert "summary:" not in text
        assert "title: 롯데 부상 소식" in text
        assert "label: INJURY_ROSTER" in text

    def test_empty_key_players(self):
        a = self._article(title="기사", event_summary="요약", key_players=[])
        text = _build_clustering_text(a)
        assert "players:" not in text

    def test_null_event_summary_field(self):
        a = {"title": "제목", "event_summary": None, "primary_label": None}
        text = _build_clustering_text(a)
        assert "title: 제목" in text
        assert "summary:" not in text

    def test_malformed_event_summary_json(self):
        a = {"title": "제목", "event_summary": "NOT_JSON", "primary_label": None}
        text = _build_clustering_text(a)
        assert "title: 제목" in text
        assert "summary:" not in text

    def test_all_empty(self):
        text = _build_clustering_text({"title": None, "event_summary": None, "primary_label": None})
        assert text == ""


# ---------------------------------------------------------------------------
# _cosine_similarity_matrix
# ---------------------------------------------------------------------------

class TestCosineSimilarityMatrix:
    def test_identical_vectors(self):
        v = np.array([[1.0, 0.0], [1.0, 0.0]])
        sim = _cosine_similarity_matrix(v)
        assert sim[0, 1] == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        v = np.array([[1.0, 0.0], [0.0, 1.0]])
        sim = _cosine_similarity_matrix(v)
        assert sim[0, 1] == pytest.approx(0.0, abs=1e-6)

    def test_diagonal_is_one(self):
        v = np.random.rand(5, 8)
        sim = _cosine_similarity_matrix(v)
        np.testing.assert_allclose(np.diag(sim), 1.0, atol=1e-6)

    def test_zero_vector_does_not_crash(self):
        v = np.array([[0.0, 0.0], [1.0, 0.0]])
        sim = _cosine_similarity_matrix(v)
        assert not np.any(np.isnan(sim))


# ---------------------------------------------------------------------------
# _cluster_articles — cluster membership and outlier logic
# ---------------------------------------------------------------------------

class TestClusterArticles:
    def _tight_embeddings(self, n: int, dim: int = 8, seed: int = 0) -> np.ndarray:
        rng = np.random.default_rng(seed)
        center = rng.standard_normal(dim)
        return center + rng.standard_normal((n, dim)) * 0.01

    def test_single_article(self):
        emb = np.array([[1.0, 0.0]])
        labels = _cluster_articles(emb, threshold=0.75)
        assert labels.shape == (1,)

    def test_two_identical_articles_cluster_together(self):
        emb = np.array([[1.0, 0.0], [1.0, 0.0]])
        labels = _cluster_articles(emb, threshold=0.75)
        assert labels[0] == labels[1]

    def test_two_orthogonal_articles_separate(self):
        emb = np.array([[1.0, 0.0], [0.0, 1.0]])
        labels = _cluster_articles(emb, threshold=0.75)
        assert labels[0] != labels[1]

    def test_tight_group_forms_one_cluster(self):
        emb = self._tight_embeddings(6)
        labels = _cluster_articles(emb, threshold=0.75)
        assert len(set(labels.tolist())) == 1

    def test_output_length_matches_input(self):
        emb = np.random.rand(10, 16)
        labels = _cluster_articles(emb, threshold=0.75)
        assert len(labels) == 10


# ---------------------------------------------------------------------------
# Outlier handling and cluster ranking (via run_topic_clustering internals)
# We test the ranking/outlier logic directly by replicating it.
# ---------------------------------------------------------------------------

class TestOutlierAndRankingLogic:
    """Validates that cluster_groups → sorted_clusters → outlier_raw_labels logic is correct."""

    def _make_labels(self, assignments: list[int]) -> np.ndarray:
        return np.array(assignments, dtype=int)

    def test_singleton_becomes_outlier(self):
        # cluster 0: 3 articles, cluster 1: 1 article (outlier)
        raw_labels = self._make_labels([0, 0, 0, 1])
        cluster_groups: dict[int, list[int]] = {}
        for idx, lbl in enumerate(raw_labels):
            cluster_groups.setdefault(int(lbl), []).append(idx)

        outlier_raw_labels: set[int] = set()
        cluster_id_map: dict[int, str] = {}
        date_str = "2026-05-22"

        sorted_clusters = sorted(cluster_groups.items(), key=lambda kv: -len(kv[1]))
        for rank, (raw_lbl, idxs) in enumerate(sorted_clusters, start=1):
            if len(idxs) < _MIN_CLUSTER_SIZE:
                outlier_raw_labels.add(raw_lbl)
            else:
                cluster_id_map[raw_lbl] = f"{date_str}_c{rank:02d}"

        assert 1 in outlier_raw_labels
        assert 0 not in outlier_raw_labels
        assert cluster_id_map[0] == "2026-05-22_c01"

    def test_largest_cluster_gets_rank_1(self):
        # cluster 2: 5 articles (largest), cluster 0: 3, cluster 1: 2
        raw_labels = self._make_labels([2, 2, 2, 2, 2, 0, 0, 0, 1, 1])
        cluster_groups: dict[int, list[int]] = {}
        for idx, lbl in enumerate(raw_labels):
            cluster_groups.setdefault(int(lbl), []).append(idx)

        date_str = "2026-05-22"
        sorted_clusters = sorted(cluster_groups.items(), key=lambda kv: -len(kv[1]))
        id_map = {}
        for rank, (raw_lbl, idxs) in enumerate(sorted_clusters, start=1):
            if len(idxs) >= _MIN_CLUSTER_SIZE:
                id_map[raw_lbl] = f"{date_str}_c{rank:02d}"

        assert id_map[2] == "2026-05-22_c01"
        assert id_map[0] == "2026-05-22_c02"
        assert id_map[1] == "2026-05-22_c03"

    def test_point_row_is_outlier_when_cluster_too_small(self):
        # Simulate the point_rows construction for a singleton cluster
        raw_labels = self._make_labels([0, 1])  # cluster 0: 1 article, cluster 1: 1 article
        cluster_groups = {0: [0], 1: [1]}
        outlier_raw_labels = {0, 1}  # both singletons
        cluster_id_map: dict[int, str] = {}
        coords = np.array([[0.1, 0.2], [0.3, 0.4]])
        date_str = "2026-05-22"
        articles = [{"id": 10}, {"id": 11}]

        point_rows = []
        for idx, article in enumerate(articles):
            raw_lbl = int(raw_labels[idx])
            is_outlier = raw_lbl in outlier_raw_labels
            cluster_id_str = None if is_outlier else cluster_id_map.get(raw_lbl)
            point_rows.append({
                "article_id": article["id"],
                "cluster_id": cluster_id_str,
                "is_outlier": is_outlier,
                "x": coords[idx, 0],
                "y": coords[idx, 1],
            })

        assert all(p["is_outlier"] for p in point_rows)
        assert all(p["cluster_id"] is None for p in point_rows)


# ---------------------------------------------------------------------------
# _project_2d — returns correct model key
# ---------------------------------------------------------------------------

class TestProjection2D:
    def _embeddings(self, n: int = 15, dim: int = 32) -> np.ndarray:
        return np.random.default_rng(0).standard_normal((n, dim))

    def test_returns_tuple_of_coords_and_key(self):
        emb = self._embeddings()
        result = _project_2d(emb)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_coords_shape(self):
        emb = self._embeddings(20)
        coords, _ = _project_2d(emb)
        assert coords.shape == (20, 2)

    def test_model_key_is_known_value(self):
        emb = self._embeddings()
        _, key = _project_2d(emb)
        assert key in (_PROJECTION_MODEL_UMAP, _PROJECTION_MODEL_PCA)

    def test_pca_fallback_key(self, monkeypatch):
        import sys
        # Simulate umap-learn not installed by hiding it from import
        monkeypatch.setitem(sys.modules, "umap", None)
        emb = self._embeddings()
        _, key = _project_2d(emb)
        assert key == _PROJECTION_MODEL_PCA

    def test_coords_are_finite(self):
        emb = self._embeddings()
        coords, _ = _project_2d(emb)
        assert np.all(np.isfinite(coords))


# ---------------------------------------------------------------------------
# _derive_cluster_summary
# ---------------------------------------------------------------------------

class TestDeriveClusterSummary:
    def _article(self, article_id, title, event_summary=None, key_players=None):
        blob = {}
        if event_summary:
            blob["event_summary"] = event_summary
        if key_players:
            blob["key_players"] = key_players
        return {
            "id": article_id,
            "title": title,
            "event_summary": json.dumps(blob) if blob else None,
        }

    def test_picks_representative_with_longest_summary(self):
        articles = [
            self._article(1, "짧은 제목", event_summary="요약"),
            self._article(2, "긴 요약 제목", event_summary="훨씬 더 긴 이벤트 요약 문장입니다"),
        ]
        summary = _derive_cluster_summary(articles, Counter({"MATCH_RELATED": 2}))
        assert summary["representative_article_id"] == 2

    def test_top_players_deduplicated_and_ranked(self):
        articles = [
            self._article(1, "A", key_players=["박세웅", "전준우"]),
            self._article(2, "B", key_players=["박세웅", "안치홍"]),
            self._article(3, "C", key_players=["박세웅"]),
        ]
        summary = _derive_cluster_summary(articles, Counter())
        assert summary["key_players"][0] == "박세웅"

    def test_dominant_label_from_counter(self):
        articles = [self._article(1, "제목")]
        summary = _derive_cluster_summary(articles, Counter({"MATCH_RELATED": 3, "ETC": 1}))
        assert summary["label_hint"] == "MATCH_RELATED"

    def test_article_count_matches(self):
        articles = [self._article(i, f"제목{i}") for i in range(5)]
        summary = _derive_cluster_summary(articles, Counter())
        assert summary["article_count"] == 5

    def test_title_truncated_to_200(self):
        long_title = "가" * 300
        articles = [self._article(1, long_title)]
        summary = _derive_cluster_summary(articles, Counter())
        assert len(summary["title"]) <= 200

    def test_summary_falls_back_to_title_when_no_event_summary(self):
        articles = [self._article(1, "fallback 제목")]
        summary = _derive_cluster_summary(articles, Counter())
        assert summary["summary"] == "fallback 제목"


# ---------------------------------------------------------------------------
# _replace_topic_map — RPC write path
# ---------------------------------------------------------------------------

class TestReplaceTopicMap:
    """Verifies that _replace_topic_map calls the RPC with the expected shape."""

    def _mock_supabase(self):
        mock_sb = MagicMock()
        mock_sb.rpc.return_value.execute.return_value = MagicMock()
        return mock_sb

    def test_rpc_called_once(self):
        mock_sb = self._mock_supabase()
        with patch("batch.topic_clusterer.supabase", mock_sb):
            _replace_topic_map(
                "2026-05-22",
                {
                    "2026-05-22_c01": {
                        "article_count": 3,
                        "representative_article_id": "aaaaaaaa-0000-0000-0000-000000000001",
                        "title": "클러스터 제목",
                        "summary": "요약",
                        "label_hint": "MATCH_RELATED",
                        "key_players": ["박세웅"],
                    }
                },
                [
                    {
                        "map_date": "2026-05-22",
                        "article_id": "aaaaaaaa-0000-0000-0000-000000000001",
                        "cluster_id": "2026-05-22_c01",
                        "cluster_rank": 1,
                        "x": 0.1,
                        "y": 0.2,
                        "embedding_model": "roberta_mean_pool_v1",
                        "projection_model": "umap_v1",
                        "is_outlier": False,
                    }
                ],
            )

        mock_sb.rpc.assert_called_once()
        call_args = mock_sb.rpc.call_args
        assert call_args[0][0] == "replace_topic_map"
        payload = call_args[0][1]
        assert payload["p_map_date"] == "2026-05-22"
        assert len(payload["p_clusters"]) == 1
        assert len(payload["p_points"]) == 1

    def test_rpc_cluster_row_has_required_fields(self):
        mock_sb = self._mock_supabase()
        with patch("batch.topic_clusterer.supabase", mock_sb):
            _replace_topic_map(
                "2026-05-22",
                {
                    "2026-05-22_c01": {
                        "article_count": 2,
                        "representative_article_id": "aaaaaaaa-0000-0000-0000-000000000002",
                        "title": "T",
                        "summary": "S",
                        "label_hint": None,
                        "key_players": [],
                    }
                },
                [],
            )

        payload = mock_sb.rpc.call_args[0][1]
        cluster = payload["p_clusters"][0]
        for field in ("id", "article_count", "representative_article_id", "title", "summary", "key_players"):
            assert field in cluster, f"Missing field: {field}"

    def test_rpc_empty_clusters_and_points(self):
        mock_sb = self._mock_supabase()
        with patch("batch.topic_clusterer.supabase", mock_sb):
            _replace_topic_map("2026-05-22", {}, [])

        payload = mock_sb.rpc.call_args[0][1]
        assert payload["p_clusters"] == []
        assert payload["p_points"] == []


# ---------------------------------------------------------------------------
# run_topic_clustering — integration-level (DB and model mocked)
# ---------------------------------------------------------------------------

class TestRunTopicClustering:
    """Covers the end-to-end run path: fetch → filter → embed → cluster → write."""

    def _make_article(self, article_id: str, is_lotte_related: bool = True) -> dict:
        blob = {
            "is_lotte_related": is_lotte_related,
            "event_summary": "롯데가 이겼습니다" if is_lotte_related else "",
            "key_players": ["박세웅"] if is_lotte_related else [],
        }
        return {
            "id": article_id,
            "title": f"기사 {article_id}",
            "event_summary": json.dumps(blob),
            "article_labels": [{"label": "MATCH_RELATED", "confidence": 0.9}],
        }

    def _mock_supabase_fetch(self, articles: list[dict]):
        mock_sb = MagicMock()
        (
            mock_sb.table.return_value
            .select.return_value
            .gte.return_value
            .lte.return_value
            .execute.return_value
        ) = MagicMock(data=articles)
        mock_sb.rpc.return_value.execute.return_value = MagicMock()
        return mock_sb

    def test_skips_when_too_few_articles(self):
        articles = [self._make_article(f"id-{i}") for i in range(_MIN_ARTICLES - 1)]
        mock_sb = self._mock_supabase_fetch(articles)
        with patch("batch.topic_clusterer.supabase", mock_sb):
            run_topic_clustering()
        mock_sb.rpc.assert_not_called()

    def test_skips_non_lotte_articles(self):
        # Only 2 is_lotte_related articles — below _MIN_ARTICLES
        articles = [self._make_article("lotte-1"), self._make_article("lotte-2")]
        articles += [self._make_article(f"other-{i}", is_lotte_related=False) for i in range(20)]
        mock_sb = self._mock_supabase_fetch(articles)
        with patch("batch.topic_clusterer.supabase", mock_sb):
            run_topic_clustering()
        mock_sb.rpc.assert_not_called()

    def test_skips_when_embedder_unavailable(self):
        articles = [self._make_article(f"id-{i}") for i in range(_MIN_ARTICLES + 5)]
        mock_sb = self._mock_supabase_fetch(articles)
        with (
            patch("batch.topic_clusterer.supabase", mock_sb),
            patch("batch.topic_clusterer._embed_texts", return_value=None),
        ):
            run_topic_clustering()
        mock_sb.rpc.assert_not_called()

    def test_calls_rpc_when_sufficient_articles(self):
        n = _MIN_ARTICLES + 5
        articles = [self._make_article(f"id-{i}") for i in range(n)]
        mock_sb = self._mock_supabase_fetch(articles)
        fake_embeddings = np.random.default_rng(0).standard_normal((n, 16))
        fake_labels = np.zeros(n, dtype=int)
        fake_coords = np.zeros((n, 2))
        with (
            patch("batch.topic_clusterer.supabase", mock_sb),
            patch("batch.topic_clusterer._embed_texts", return_value=fake_embeddings),
            patch("batch.topic_clusterer._cluster_articles", return_value=fake_labels),
            patch("batch.topic_clusterer._project_2d", return_value=(fake_coords, "umap_v1")),
        ):
            run_topic_clustering()
        mock_sb.rpc.assert_called_once()
        assert mock_sb.rpc.call_args[0][0] == "replace_topic_map"

    def test_db_write_failure_does_not_raise(self):
        n = _MIN_ARTICLES + 5
        articles = [self._make_article(f"id-{i}") for i in range(n)]
        mock_sb = self._mock_supabase_fetch(articles)
        mock_sb.rpc.return_value.execute.side_effect = RuntimeError("DB error")
        fake_embeddings = np.random.default_rng(0).standard_normal((n, 16))
        fake_labels = np.zeros(n, dtype=int)
        fake_coords = np.zeros((n, 2))
        with (
            patch("batch.topic_clusterer.supabase", mock_sb),
            patch("batch.topic_clusterer._embed_texts", return_value=fake_embeddings),
            patch("batch.topic_clusterer._cluster_articles", return_value=fake_labels),
            patch("batch.topic_clusterer._project_2d", return_value=(fake_coords, "umap_v1")),
        ):
            run_topic_clustering()  # must not raise
