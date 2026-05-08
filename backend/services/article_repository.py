import json
from datetime import date

from core.database import supabase
from core.time_utils import utc_day_bounds


_RELATION_ID_LIMIT = 10_000


def _reshape_article(raw: dict) -> dict:
    article = dict(raw)

    # article_labels [{label, confidence}] → primary_label, confidence (highest confidence wins)
    labels: list[dict] = article.pop("article_labels", None) or []
    if labels:
        best = max(labels, key=lambda x: x.get("confidence") or 0.0)
        article["primary_label"] = best.get("label")
        article["confidence"] = best.get("confidence")
    else:
        article["primary_label"] = None
        article["confidence"] = None

    # event_summary JSON string → event_summary text + lotte_stance + key_players
    raw_summary = article.get("event_summary")
    if raw_summary:
        try:
            parsed = json.loads(raw_summary)
            article["event_summary"] = parsed.get("event_summary") or None
            article["lotte_stance"] = parsed.get("lotte_stance") or None
            article["key_players"] = parsed.get("key_players") or []
        except (json.JSONDecodeError, TypeError, AttributeError):
            article["lotte_stance"] = None
            article["key_players"] = []
    else:
        article["lotte_stance"] = None
        article["key_players"] = []

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
    return [row["article_id"] for row in result.data]


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
