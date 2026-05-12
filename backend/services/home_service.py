"""
Server-side aggregation for GET /reports/home.
"""

import json
import logging
from datetime import date

from services import report_repository

logger = logging.getLogger(__name__)

_SENTIMENT_VALUES = {"긍정", "부정", "중립"}


def _parse_event_summary(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _primary_label(article: dict) -> str | None:
    labels: list[dict] = article.get("article_labels") or []
    if not labels:
        return None
    best = max(labels, key=lambda x: x.get("confidence") or 0.0)
    return best.get("label")


def _compute_label_counts(articles: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {
        "MATCH_RELATED": 0,
        "INJURY_ROSTER": 0,
        "TRANSACTION_CONTRACT": 0,
        "PERFORMANCE_ANALYSIS": 0,
        "INTERVIEW": 0,
        "CLUB_OPERATION": 0,
        "ETC": 0,
    }
    for article in articles:
        label = _primary_label(article)
        if label in counts:
            counts[label] += 1
    return counts


def _compute_sentiment(articles: list[dict]) -> dict:
    positive = neutral = negative = 0
    for article in articles:
        parsed = _parse_event_summary(article.get("event_summary"))
        stance = parsed.get("lotte_stance", "")
        if stance == "긍정":
            positive += 1
        elif stance == "부정":
            negative += 1
        elif stance == "중립":
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
        if _primary_label(a) == lead_label
    ]

    summaries: list[str] = []
    all_key_players: list[str] = []

    for a in lead_articles:
        parsed = _parse_event_summary(a.get("event_summary"))
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
    articles = report_repository.fetch_articles_for_day(target_date)
    article_ids = [a["id"] for a in articles]

    mentions = report_repository.fetch_player_mentions_with_position(article_ids)
    team_report = report_repository.get_report("team_daily_report", target_date)
    game = report_repository.fetch_game_for_day(target_date)

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
        "game_context": game,
    }
