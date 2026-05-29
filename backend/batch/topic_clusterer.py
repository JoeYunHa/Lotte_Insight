"""
Daily topic map computation: embed articles → cluster → project to 2D.

Embedding: KoELECTRA mean pooling (reuses the existing classifier model dir).
Clustering: agglomerative clustering on cosine distance.
Projection: UMAP (falls back to PCA if umap-learn is not installed).

Run after news_collector.py, once per day:
  python -m batch.topic_clusterer           # today (KST)
  python -m batch.topic_clusterer 2026-05-22
"""

import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

from core.database import supabase
from core.time_utils import today_kst, utc_day_bounds
from models.runtime import LazyArtifactsLoader, ModelArtifacts
from services.article_utils import parse_event_summary_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_ARTICLES = 10           # skip clustering if fewer articles than this
_SIMILARITY_THRESHOLD = 0.75  # cosine similarity; articles above this merge into one cluster
_MIN_CLUSTER_SIZE = 2        # clusters smaller than this become outliers
_UMAP_RANDOM_STATE = 42      # fixed for reproducible 2D coordinates
_EMBED_BATCH_SIZE = 32
_EMBED_MAX_LENGTH = 128
_EMBEDDING_MODEL_KEY = "koelectra_mean_pool_v1"
_PROJECTION_MODEL_UMAP = "umap_v1"
_PROJECTION_MODEL_PCA = "pca_v1"
_MAX_AGGLOMERATIVE_ARTICLES = 400


# ---------------------------------------------------------------------------
# Embedder — KoELECTRA mean pooling
#
# Reuses the classifier model dir (CLASSIFIER_MODEL_DIR / classifier_koelectra).
# AutoModel loads the base ELECTRA encoder; the classification head weights
# in the checkpoint are silently ignored (not part of AutoModel's structure).
# ---------------------------------------------------------------------------

def _load_embedder(model_dir: Path) -> ModelArtifacts:
    import torch
    from transformers import AutoModel, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModel.from_pretrained(str(model_dir), ignore_mismatched_sizes=True).to(device)
    model.eval()
    logger.info("Loaded KoELECTRA embedder from %s (device=%s)", model_dir, device)
    return ModelArtifacts(model=model, tokenizer=tokenizer, device=device)


_embedder = LazyArtifactsLoader(
    current_file=__file__,
    env_var="CLASSIFIER_MODEL_DIR",
    deployed_dir_name="classifier_koelectra",
    training_dir_name="classifier_koelectra",
    required_file="config.json",
    loader=_load_embedder,
    missing_log="KoELECTRA embedder not found; topic clustering skipped.",
    error_log="Failed to load KoELECTRA embedder (%s); topic clustering skipped.",
)


def _mean_pool(token_embeddings: "torch.Tensor", attention_mask: "torch.Tensor") -> "torch.Tensor":
    mask = attention_mask.unsqueeze(-1).float()
    return (token_embeddings * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


def _embed_texts(texts: list[str]) -> np.ndarray | None:
    artifacts = _embedder.get()
    if artifacts is None:
        return None
    if not texts:
        return np.empty((0, 0), dtype=float)

    import torch

    all_vecs: list[np.ndarray] = []
    for start in range(0, len(texts), _EMBED_BATCH_SIZE):
        chunk = texts[start : start + _EMBED_BATCH_SIZE]
        enc = artifacts.tokenizer(
            chunk,
            truncation=True,
            padding=True,
            max_length=_EMBED_MAX_LENGTH,
            return_tensors="pt",
        )
        enc = {k: v.to(artifacts.device) for k, v in enc.items()}
        with torch.no_grad():
            outputs = artifacts.model(**enc)
        vecs = _mean_pool(outputs.last_hidden_state, enc["attention_mask"])
        all_vecs.append(vecs.cpu().numpy())

    if not all_vecs:
        return np.empty((0, 0), dtype=float)
    return np.vstack(all_vecs)


# ---------------------------------------------------------------------------
# Clustering text builder
# ---------------------------------------------------------------------------

def _build_clustering_text(article: dict) -> str:
    blob = parse_event_summary_json(article.get("event_summary"))
    event_text = (blob.get("event_summary") or "").strip()
    key_players = blob.get("key_players") or []

    title = (article.get("title") or "").strip()
    primary_label = (article.get("primary_label") or "").strip()
    players_str = ", ".join(key_players) if key_players else ""

    parts: list[str] = []
    if event_text:
        parts.append(f"summary: {event_text}")
    if title:
        parts.append(f"title: {title}")
    if primary_label:
        parts.append(f"label: {primary_label}")
    if players_str:
        parts.append(f"players: {players_str}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Clustering — agglomerative on cosine distance
# ---------------------------------------------------------------------------

def _cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / np.where(norms > 0, norms, 1.0)
    return normalized @ normalized.T


def _cluster_articles(embeddings: np.ndarray, threshold: float) -> np.ndarray:
    n = len(embeddings)
    if n < 2:
        return np.zeros(n, dtype=int)

    try:
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.cluster import MiniBatchKMeans

        # Agglomerative clustering is O(n^2). Use it for moderate sizes only.
        if n <= _MAX_AGGLOMERATIVE_ARTICLES:
            clustering = AgglomerativeClustering(
                n_clusters=None,
                metric="cosine",
                linkage="average",
                distance_threshold=1.0 - threshold,
            )
            return clustering.fit_predict(embeddings)

        # For large batches, use minibatch k-means to avoid quadratic memory/time.
        cluster_count = max(2, int(np.sqrt(n / 2)))
        logger.warning(
            "Article count %d exceeds agglomerative threshold %d; using MiniBatchKMeans(k=%d).",
            n,
            _MAX_AGGLOMERATIVE_ARTICLES,
            cluster_count,
        )
        model = MiniBatchKMeans(
            n_clusters=cluster_count,
            random_state=_UMAP_RANDOM_STATE,
            batch_size=min(256, n),
            n_init="auto",
        )
        return model.fit_predict(embeddings)
    except ImportError:
        logger.warning("sklearn not installed; using greedy centroid clustering fallback.")
        # Greedy centroid assignment avoids building an O(n^2) similarity matrix.
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / np.where(norms > 0, norms, 1.0)
        centroids: list[np.ndarray] = []
        centroid_sizes: list[int] = []
        labels = np.empty(n, dtype=int)

        for i, vec in enumerate(normalized):
            best_idx = -1
            best_sim = -1.0
            for idx, centroid in enumerate(centroids):
                sim = float(np.dot(vec, centroid))
                if sim > best_sim:
                    best_sim = sim
                    best_idx = idx

            if best_idx >= 0 and best_sim >= threshold:
                labels[i] = best_idx
                size = centroid_sizes[best_idx]
                centroids[best_idx] = (centroids[best_idx] * size + vec) / (size + 1)
                centroid_sizes[best_idx] = size + 1
            else:
                labels[i] = len(centroids)
                centroids.append(vec.copy())
                centroid_sizes.append(1)

        return labels


# ---------------------------------------------------------------------------
# 2D projection — UMAP with PCA fallback
# Returns (coordinates, actual_model_key) to avoid recording wrong metadata.
# ---------------------------------------------------------------------------

def _project_2d(embeddings: np.ndarray) -> tuple[np.ndarray, str]:
    n = len(embeddings)
    try:
        import umap  # umap-learn

        n_neighbors = max(2, min(15, n - 1))
        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=n_neighbors,
            min_dist=0.1,
            metric="cosine",
            random_state=_UMAP_RANDOM_STATE,
        )
        coords = reducer.fit_transform(embeddings).astype(float)
        return coords, _PROJECTION_MODEL_UMAP
    except ImportError:
        logger.warning("umap-learn not installed; falling back to PCA for 2D projection.")
        try:
            from sklearn.decomposition import PCA

            pca = PCA(n_components=2, random_state=_UMAP_RANDOM_STATE)
            coords = pca.fit_transform(embeddings).astype(float)
            return coords, _PROJECTION_MODEL_PCA
        except ImportError:
            logger.warning("sklearn PCA unavailable; falling back to numpy SVD projection.")
            centered = embeddings - embeddings.mean(axis=0, keepdims=True)
            _, _, vt = np.linalg.svd(centered, full_matrices=False)
            coords = centered @ vt[:2].T
            return coords.astype(float), _PROJECTION_MODEL_PCA


# ---------------------------------------------------------------------------
# Cluster summary derivation
# ---------------------------------------------------------------------------

def _derive_cluster_summary(cluster_articles: list[dict], label_counts: Counter) -> dict:
    def summary_len(a: dict) -> int:
        blob = parse_event_summary_json(a.get("event_summary"))
        return len(blob.get("event_summary") or "")

    representative = max(cluster_articles, key=summary_len)

    all_players: list[str] = []
    for a in cluster_articles:
        blob = parse_event_summary_json(a.get("event_summary"))
        all_players.extend(blob.get("key_players") or [])
    top_players = [p for p, _ in Counter(all_players).most_common(5)]

    dominant_label = label_counts.most_common(1)[0][0] if label_counts else None
    rep_blob = parse_event_summary_json(representative.get("event_summary"))
    summary_text = (rep_blob.get("event_summary") or representative.get("title") or "").strip()

    return {
        "representative_article_id": representative["id"],
        "title": (representative.get("title") or "")[:200],
        "summary": summary_text[:400],
        "label_hint": dominant_label,
        "key_players": top_players,
        "article_count": len(cluster_articles),
    }


# ---------------------------------------------------------------------------
# DB write — single RPC call wraps delete+insert in one server-side transaction
# ---------------------------------------------------------------------------

def _replace_topic_map(map_date: str, clusters: dict[str, dict], points: list[dict]) -> None:
    """
    Atomically replace all topic map data for map_date via the replace_topic_map RPC.
    The server-side function executes delete + insert inside a single transaction,
    so a mid-write failure never leaves the date's data partially wiped.
    """
    cluster_rows = [
        {
            "id": cluster_id,
            "article_count": meta["article_count"],
            "representative_article_id": str(meta["representative_article_id"]),
            "title": meta["title"],
            "summary": meta["summary"],
            "label_hint": meta["label_hint"],
            "key_players": meta["key_players"],
        }
        for cluster_id, meta in clusters.items()
    ]

    point_rows = [
        {
            **p,
            "cluster_id": p.get("cluster_id"),   # may be None (outlier)
            "cluster_rank": p.get("cluster_rank"),
        }
        for p in points
    ]

    supabase.rpc(
        "replace_topic_map",
        {
            "p_map_date": map_date,
            "p_clusters": cluster_rows,
            "p_points": point_rows,
        },
    ).execute()
    logger.info(
        "replace_topic_map RPC: %d clusters, %d points for %s",
        len(cluster_rows),
        len(point_rows),
        map_date,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_topic_clustering(target_date: date | None = None) -> None:
    """
    Compute topic map for target_date (defaults to today KST).

    Steps:
      1. Fetch is_lotte_related articles for the day from Supabase
      2. Build clustering text (event_summary + title + label + key_players)
      3. Embed with KoELECTRA mean pooling
      4. Cluster with agglomerative clustering (cosine similarity threshold)
      5. Project to 2D with UMAP (PCA fallback); record actual model key used
      6. Derive cluster summaries
      7. Delete existing map rows for the date, then insert fresh results
    """
    if target_date is None:
        target_date = today_kst()

    date_str = target_date.isoformat()
    start_at, end_at = utc_day_bounds(target_date)

    # 1. Fetch articles with labels
    resp = (
        supabase.table("articles")
        .select("id, title, event_summary, article_labels(label, confidence)")
        .gte("published_at", start_at)
        .lte("published_at", end_at)
        .execute()
    )
    raw_articles = resp.data or []

    # Keep only is_lotte_related=True (parsed from event_summary JSON)
    articles: list[dict] = []
    for a in raw_articles:
        blob = parse_event_summary_json(a.get("event_summary"))
        if blob.get("is_lotte_related") is True:
            labels = a.get("article_labels") or []
            best = max(labels, key=lambda x: x.get("confidence") or 0.0) if labels else {}
            a["primary_label"] = best.get("label")
            articles.append(a)

    n = len(articles)
    logger.info("Topic clustering: %d is_lotte_related articles on %s", n, date_str)

    if n < _MIN_ARTICLES:
        logger.info("Too few articles (%d < %d); skipping topic map.", n, _MIN_ARTICLES)
        return

    # 2. Build clustering texts
    texts = [_build_clustering_text(a) for a in articles]

    # 3. Embed
    embeddings = _embed_texts(texts)
    if embeddings is None:
        logger.warning("Embedding unavailable; aborting topic clustering.")
        return

    # 4. Cluster
    raw_labels = _cluster_articles(embeddings, threshold=_SIMILARITY_THRESHOLD)

    # 5. Project to 2D — actual_projection_key reflects whether UMAP or PCA was used
    coords, actual_projection_key = _project_2d(embeddings)

    # 6. Rank clusters by size; mark singletons as outliers
    cluster_groups: dict[int, list[int]] = {}
    for idx, lbl in enumerate(raw_labels):
        cluster_groups.setdefault(int(lbl), []).append(idx)

    sorted_clusters = sorted(cluster_groups.items(), key=lambda kv: -len(kv[1]))

    cluster_id_map: dict[int, str] = {}
    outlier_raw_labels: set[int] = set()
    cluster_meta: dict[str, dict] = {}

    for rank, (raw_lbl, idxs) in enumerate(sorted_clusters, start=1):
        if len(idxs) < _MIN_CLUSTER_SIZE:
            outlier_raw_labels.add(raw_lbl)
            continue

        cluster_id_str = f"{date_str}_c{rank:02d}"
        cluster_id_map[raw_lbl] = cluster_id_str

        cluster_articles = [articles[i] for i in idxs]
        label_counts = Counter(
            a["primary_label"] for a in cluster_articles if a.get("primary_label")
        )
        cluster_meta[cluster_id_str] = _derive_cluster_summary(cluster_articles, label_counts)

    # 7. Build point rows
    point_rows: list[dict] = []
    for idx, article in enumerate(articles):
        raw_lbl = int(raw_labels[idx])
        is_outlier = raw_lbl in outlier_raw_labels
        cluster_id_str = None if is_outlier else cluster_id_map.get(raw_lbl)
        cluster_rank_val = int(cluster_id_str.split("_c")[-1]) if cluster_id_str else None

        point_rows.append({
            "map_date": date_str,
            "article_id": article["id"],
            "cluster_id": cluster_id_str,
            "cluster_rank": cluster_rank_val,
            "x": round(float(coords[idx, 0]), 6),
            "y": round(float(coords[idx, 1]), 6),
            "embedding_model": _EMBEDDING_MODEL_KEY,
            "projection_model": actual_projection_key,
            "is_outlier": is_outlier,
        })

    # 8. Replace (delete + insert) — idempotent on rerun
    try:
        _replace_topic_map(date_str, cluster_meta, point_rows)
        logger.info(
            "Topic map complete: %d points, %d clusters, %d outliers on %s",
            len(point_rows),
            len(cluster_meta),
            sum(1 for p in point_rows if p["is_outlier"]),
            date_str,
        )
    except Exception as exc:  # noqa: BLE001 - DB write boundary
        logger.error("Failed to write topic map to DB: %s", exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    target: date | None = None
    if len(sys.argv) > 1:
        try:
            target = date.fromisoformat(sys.argv[1])
        except ValueError:
            logger.error("Invalid date '%s'. Expected YYYY-MM-DD.", sys.argv[1])
            sys.exit(1)
    run_topic_clustering(target)
