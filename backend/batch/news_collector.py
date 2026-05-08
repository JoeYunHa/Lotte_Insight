"""
Collect Lotte Giants news articles from Naver Search API.

- `description` is used only as classifier context.
- Articles are upserted by `source_url` to avoid duplicates.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from core.config import settings
from core.database import supabase
from models.classifier import classify
from models.player_extractor import extract_players
from models.summarizer import summarize as summarize_article
from services.player_catalog import list_player_names

logger = logging.getLogger(__name__)

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
BASE_KEYWORDS = [f"{settings.team_name_ko} 자이언츠"]


def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _source_name(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _fetch_news(keyword: str, display: int = 100) -> list[dict]:
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    params = {"query": keyword, "display": display, "sort": "date"}
    response = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    return response.json().get("items", [])


def _upsert_articles(items: list[dict]) -> int:
    rows = []
    for item in items:
        title = _clean_html(item.get("title", ""))
        link = item.get("originallink") or item.get("link", "")
        if not title or not link:
            continue

        pub_str = item.get("pubDate", "")
        try:
            published_at = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %z").isoformat()
        except (ValueError, TypeError):
            published_at = datetime.now(timezone.utc).isoformat()

        rows.append(
            {
                "source_url": link,
                "source_name": _source_name(link),
                "title": title,
                "published_at": published_at,
            }
        )

    if not rows:
        return 0

    result = supabase.table("articles").upsert(rows, on_conflict="source_url").execute()
    return len(result.data)


def _label_and_link_players(items: list[dict]):
    for item in items:
        title = _clean_html(item.get("title", ""))
        description = _clean_html(item.get("description", ""))[
            : settings.article_description_snippet_length
        ]
        link = item.get("originallink") or item.get("link", "")
        if not link:
            continue

        result = supabase.table("articles").select("id").eq("source_url", link).limit(1).execute()
        if not result.data:
            continue
        article_id = result.data[0]["id"]

        pub_str = item.get("pubDate", "")
        try:
            published_at = datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            published_at = ""

        label_result = classify(title, description)
        supabase.table("article_labels").upsert(
            {
                "article_id": article_id,
                "label": label_result["label"],
                "confidence": label_result["confidence"],
            },
            on_conflict="article_id",
        ).execute()

        summary_result = summarize_article(
            title=title,
            description_snippet=description,
            primary_label=label_result["label"],
            published_at=published_at,
        )
        event_summary = summary_result.get("event_summary", "")
        if event_summary:
            supabase.table("articles").update({"event_summary": event_summary}).eq("id", article_id).execute()

        player_ids = extract_players(title)
        if player_ids:
            player_rows = [{"article_id": article_id, "player_id": player_id} for player_id in player_ids]
            supabase.table("article_players").upsert(
                player_rows,
                on_conflict="article_id,player_id",
            ).execute()


def run() -> int:
    logger.info("News collection started")

    keywords = BASE_KEYWORDS + [
        f"{settings.team_name_ko} {name}"
        for name in list_player_names()[: settings.article_keyword_limit]
    ]

    all_items: list[dict] = []
    for keyword in keywords:
        try:
            items = _fetch_news(keyword)
            all_items.extend(items)
            logger.info("Collected %s items for keyword %s", len(items), keyword)
        except Exception as exc:
            logger.error("Failed to collect keyword %s: %s", keyword, exc)

    seen: set[str] = set()
    unique_items: list[dict] = []
    for item in all_items:
        url = item.get("originallink") or item.get("link", "")
        if url and url not in seen:
            seen.add(url)
            unique_items.append(item)

    _upsert_articles(unique_items)
    _label_and_link_players(unique_items)

    logger.info("News collection completed: %s items", len(unique_items))
    return len(unique_items)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    count = run()
    print(f"Processed articles: {count}")
    sys.exit(0)
