from datetime import date
import logging

from core import cache
from core.database import supabase
from services.article_utils import VALID_LABEL_KEYS, select_primary_label_and_confidence
from services.cache_keys import CacheKeyBuilder

logger = logging.getLogger(__name__)


def get_topic_map(map_date: date) -> dict | None:
    """Fetch clusters and article points for the given KST date.

    Returns None when no clusters exist for the date (pipeline not yet run).
    Negative results (None) are not cached — the batch may not have run yet.
    """
    cache_key = CacheKeyBuilder.topic_map(map_date=map_date)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    date_str = map_date.isoformat()

    clusters_res = (
        supabase.table("topic_clusters")
        .select(
            "id, map_date, article_count, representative_article_id, "
            "title, summary, label_hint, key_players, created_at, updated_at"
        )
        .eq("map_date", date_str)
        .order("article_count", desc=True)
        .execute()
    )
    clusters = clusters_res.data or []
    if not clusters:
        return None

    points_res = (
        supabase.table("article_topic_points")
        .select(
            "article_id, cluster_id, cluster_rank, x, y, is_outlier, "
            "articles(id, title, source_name, published_at, "
            "article_labels(label, confidence))"
        )
        .eq("map_date", date_str)
        .order("cluster_rank", nullsfirst=False)
        .execute()
    )
    raw_points = points_res.data or []

    result = {
        "map_date": date_str,
        "clusters": _reshape_clusters(clusters),
        "points": _reshape_points(raw_points),
    }
    cache.set_json(cache_key, result, cache.ttl_seconds(map_date))
    return result


def _reshape_clusters(clusters: list[dict]) -> list[dict]:
    result = []
    for c in clusters:
        rep_id = c.get("representative_article_id")
        result.append({
            "id": c["id"],
            "map_date": c["map_date"],
            "article_count": c["article_count"],
            "representative_article_id": str(rep_id) if rep_id else None,
            "title": c.get("title") or "",
            "summary": c.get("summary") or "",
            "label_hint": c.get("label_hint"),
            "key_players": c.get("key_players") or [],
            "created_at": c["created_at"],
            "updated_at": c["updated_at"],
        })
    return result


def _reshape_points(raw_points: list[dict]) -> list[dict]:
    result = []
    for row in raw_points:
        article_raw = row.get("articles")
        article = None
        if article_raw:
            labels = article_raw.get("article_labels") or []
            raw_label, _ = select_primary_label_and_confidence(labels)
            article = {
                "id": str(article_raw["id"]),
                "title": article_raw.get("title") or "",
                "source_name": article_raw.get("source_name") or "",
                "published_at": article_raw.get("published_at") or "",
                "primary_label": raw_label if raw_label in VALID_LABEL_KEYS else None,
            }
        result.append({
            "article_id": str(row["article_id"]),
            "cluster_id": row.get("cluster_id"),
            "cluster_rank": row.get("cluster_rank"),
            "x": float(row["x"]),
            "y": float(row["y"]),
            "is_outlier": bool(row.get("is_outlier", False)),
            "article": article,
        })
    return result
