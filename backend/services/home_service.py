"""
Server-side aggregation for GET /reports/home.
"""

import logging
from datetime import date

from services import report_repository
from services.article_utils import (
    VALID_LABEL_KEYS,
    parse_event_summary_json,
    select_primary_label,
)

logger = logging.getLogger(__name__)


def _primary_label(article: dict) -> str | None:
    return select_primary_label(article.get("article_labels") or [])


def _enrich_articles(articles: list[dict]) -> list[dict]:
    """Attach parsed event_summary and primary_label once per article.

    Avoids re-parsing the JSON blob in every downstream helper (I4).
    """
    enriched: list[dict] = []
    for article in articles:
        parsed = parse_event_summary_json(article.get("event_summary"))
        enriched.append({
            **article,
            "_parsed_event_summary": parsed,
            "_primary_label": _primary_label(article),
        })
    return enriched


def _compute_label_counts(articles: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {key: 0 for key in VALID_LABEL_KEYS}
    for article in articles:
        label = article.get("_primary_label") or _primary_label(article)
        if label in counts:
            counts[label] += 1
    return counts


def _compute_sentiment(articles: list[dict]) -> dict:
    positive = neutral = negative = 0
    for article in articles:
        parsed = article.get("_parsed_event_summary") or parse_event_summary_json(
            article.get("event_summary")
        )
        stance = parsed.get("team_stance") or parsed.get("lotte_stance") or ""
        if stance == "positive":
            positive += 1
        elif stance == "negative":
            negative += 1
        elif stance == "neutral":
            neutral += 1
    analyzed = positive + neutral + negative
    # SentimentBar expects ratios (0-1), analyzed is a raw count
    return {
        "positive": positive / analyzed if analyzed else 0.0,
        "neutral": neutral / analyzed if analyzed else 0.0,
        "negative": negative / analyzed if analyzed else 0.0,
        "analyzed": analyzed,
    }


def _get_lead_label(label_counts: dict[str, int]) -> str | None:
    filtered = [(label, cnt) for label, cnt in label_counts.items() if cnt > 0]
    if not filtered:
        return None
    return max(filtered, key=lambda x: x[1])[0]


def _get_lead_story(
    articles: list[dict], lead_label: str | None
) -> tuple[str | None, list[str]]:
    if not lead_label:
        return None, []

    lead_articles = [
        a for a in articles
        if (a.get("_primary_label") or _primary_label(a)) == lead_label
    ]

    summaries: list[str] = []
    all_key_players: list[str] = []

    for a in lead_articles:
        parsed = a.get("_parsed_event_summary") or parse_event_summary_json(
            a.get("event_summary")
        )
        summary = parsed.get("event_summary") or ""
        if summary:
            summaries.append(summary)
        all_key_players.extend(parsed.get("key_players") or [])

    lead_summary = (
        max(summaries, key=len) if summaries
        else (lead_articles[0].get("title") if lead_articles else None)
    )
    # 순서 보존 중복 제거
    seen: set[str] = set()
    unique_players: list[str] = []
    for name in all_key_players:
        if name and name not in seen:
            seen.add(name)
            unique_players.append(name)

    return lead_summary, unique_players[:5]


def _compute_top_players(mentions: list[dict], limit: int = 4) -> list[dict]:
    counts: dict[int, dict] = {}
    for row in mentions:
        player_data = row.get("players") or {}
        pid = player_data.get("id") or row.get("player_id")
        if not pid:
            continue
        pid = int(pid)
        if pid not in counts:
            counts[pid] = {
                "player": {
                    "id": pid,
                    "name": player_data.get("name", ""),
                    "position": player_data.get("position", ""),
                },
                "mention_count": 0,
            }
        counts[pid]["mention_count"] += 1

    return sorted(counts.values(), key=lambda x: x["mention_count"], reverse=True)[:limit]


def build_home_report(target_date: date) -> dict:
    raw_articles = report_repository.fetch_articles_for_day(target_date)
    articles = _enrich_articles(raw_articles)
    article_ids = [a["id"] for a in articles]

    mentions = report_repository.fetch_player_mentions_with_position(article_ids)
    team_report = report_repository.get_report("team_daily_report", target_date)
    games = report_repository.fetch_games_for_day(target_date)
    primary_game = games[0] if games else None

    label_counts = _compute_label_counts(articles)
    sentiment = _compute_sentiment(articles)
    lead_label = _get_lead_label(label_counts)
    lead_summary, lead_key_players = _get_lead_story(articles, lead_label)
    top_players = _compute_top_players(mentions)

    return {
        "date": target_date.isoformat(),
        "article_count": len(articles),
        "label_counts": label_counts,
        "sentiment": sentiment,
        "lead_label": lead_label,
        "lead_summary": lead_summary,
        "lead_key_players": lead_key_players,
        "top_players": top_players,
        "team_report": team_report,
        "game_context": primary_game,
        "game_contexts": games,
    }
