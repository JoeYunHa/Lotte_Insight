from datetime import date

from core.database import supabase
from core.time_utils import utc_day_bounds
from services.article_utils import parse_event_summary_json, select_primary_label_and_confidence


def _reshape_article(raw: dict) -> dict:
    article = dict(raw)

    labels: list[dict] = article.pop("article_labels", None) or []
    best_label, best_confidence = select_primary_label_and_confidence(labels)
    article["primary_label"] = best_label
    article["confidence"] = best_confidence

    parsed = parse_event_summary_json(article.get("event_summary"))
    article["event_summary"] = parsed.get("event_summary") or None
    article["lotte_stance"] = parsed.get("lotte_stance") or None
    article["key_players"] = parsed.get("key_players") or []

    return article


def list_articles(
    *,
    article_date: date | None = None,
    label: str | None = None,
    player_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    # Use !inner (INNER JOIN) only for filtered relations so the DB computes the
    # intersection server-side — avoids client-side pagination + large IN clauses.
    labels_select = "article_labels!inner(label, confidence)" if label else "article_labels(label, confidence)"
    players_select = "article_players!inner(player_id, players(name))" if player_id else "article_players(player_id, players(name))"

    query = supabase.table("articles").select(
        f"id, source_url, source_name, title, published_at, author_name, event_summary, "
        f"{labels_select}, {players_select}"
    )

    if article_date:
        start_at, end_at = utc_day_bounds(article_date)
        query = query.gte("published_at", start_at).lte("published_at", end_at)
    if label:
        query = query.eq("article_labels.label", label)
    if player_id:
        query = query.eq("article_players.player_id", player_id)

    result = query.order("published_at", desc=True).range(offset, offset + limit - 1).execute()
    return [_reshape_article(row) for row in result.data or []]


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
