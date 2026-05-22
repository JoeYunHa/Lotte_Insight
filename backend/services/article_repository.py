from datetime import date

from core.database import supabase
from core.time_utils import utc_day_bounds
import logging

from services.article_utils import parse_event_summary_json, select_primary_label_and_confidence

logger = logging.getLogger(__name__)

_RELATION_ID_LIMIT = 10_000


def _reshape_article(raw: dict) -> dict:
    article = dict(raw)

    # article_labels [{label, confidence}] → primary_label, confidence (highest confidence wins)
    labels: list[dict] = article.pop("article_labels", None) or []
    best_label, best_confidence = select_primary_label_and_confidence(labels)
    article["primary_label"] = best_label
    article["confidence"] = best_confidence

    # event_summary JSON string → event_summary text + lotte_stance + key_players
    parsed = parse_event_summary_json(article.get("event_summary"))
    article["event_summary"] = parsed.get("event_summary") or None
    article["lotte_stance"] = parsed.get("lotte_stance") or None
    article["key_players"] = parsed.get("key_players") or []

    return article


def _article_ids_for_relation(
    relation_table: str,
    filter_column: str,
    value: int | str,
) -> list[int]:
    result = (
        supabase.table(relation_table)
        .select("article_id")
        .eq(filter_column, value)
        .limit(_RELATION_ID_LIMIT)
        .execute()
    )
    ids = [row["article_id"] for row in result.data]
    if len(ids) == _RELATION_ID_LIMIT:
        logger.warning(
            "_article_ids_for_relation hit %d-row limit on %s.%s=%r — results may be incomplete",
            _RELATION_ID_LIMIT, relation_table, filter_column, value,
        )
    return ids


def list_articles(
    *,
    article_date: date | None = None,
    label: str | None = None,
    player_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    query = supabase.table("articles").select(
        "id, source_url, source_name, title, published_at, author_name, event_summary, "
        "article_labels(label, confidence), "
        "article_players(player_id, players(name))"
    )

    if article_date:
        start_at, end_at = utc_day_bounds(article_date)
        query = query.gte("published_at", start_at).lte("published_at", end_at)

    relation_filters = (
        ("article_players", "player_id", player_id),
        ("article_labels", "label", label),
    )
    for relation_table, filter_column, value in relation_filters:
        if value is None:
            continue
        article_ids = _article_ids_for_relation(relation_table, filter_column, value)
        if not article_ids:
            return []
        query = query.in_("id", article_ids)

    result = (
        query.order("published_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [_reshape_article(row) for row in result.data]


def get_article(article_id: int) -> dict | None:
    result = (
        supabase.table("articles")
        .select("*, article_labels(*), article_players(*, players(*))")
        .eq("id", article_id)
        .maybe_single()
        .execute()
    )
    if result.data is None:
        return None
    return _reshape_article(result.data)
