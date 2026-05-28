"""
Collect Lotte Giants news articles from RSS feeds.

This module provides an alternative/supplementary data source to the Naver Search API.
RSS feeds are free, require no API keys, and provide good coverage of Korean sports news.
"""

import logging
from calendar import timegm
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

from services.article_utils import NormalizedNewsItem, clean_html, extract_source_name

logger = logging.getLogger(__name__)

# RSS feed sources
# Format: (name, url, description)
RSS_FEEDS = [
    (
        "google_news_lotte",
        "https://news.google.com/rss/search?q=%EB%A1%AF%EB%8D%B0+%EC%9E%90%EC%9D%B4%EC%96%B8%EC%B8%A0&hl=ko&gl=KR&ceid=KR:ko",
        "Google News - Lotte Giants keyword search",
    ),
    (
        "google_news_kbo",
        "https://news.google.com/rss/search?q=KBO+%EB%A1%AF%EB%8D%B0&hl=ko&gl=KR&ceid=KR:ko",
        "Google News - KBO Lotte keyword search",
    ),
    (
        "donga_sports",
        "http://rss.donga.com/sports.xml",
        "Donga Sports RSS",
    ),
    (
        "khan_baseball",
        "https://sports.khan.co.kr/rss/baseball",
        "Khan Sports baseball RSS",
    ),
    (
        "yonhap_sports",
        "https://www.yna.co.kr/rss/sports.xml",
        "Yonhap Sports RSS",
    ),
]

# Keywords to filter Lotte-related articles
LOTTE_KEYWORDS = [
    "\ub86f\ub370",
    "lotte",
    "\uc790\uc774\uc5b8\uce20",
    "giants",
    "\uc0ac\uc9c1",
    "sajik",
]

_REQUEST_TIMEOUT = 10


@dataclass(frozen=True)
class RSSFeedConfig:
    """Configuration for an RSS feed source."""

    name: str
    url: str
    description: str
    verify_ssl: bool = True


def _parse_rss_pubdate(entry: Any) -> datetime:
    """Parse publication date from RSS entry."""
    time_struct = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )

    if time_struct:
        try:
            timestamp = timegm(time_struct)
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            pass

    return datetime.now(timezone.utc)


def _contains_lotte_keyword(text: str) -> bool:
    """Check if text contains any Lotte-related keyword (case-insensitive)."""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in LOTTE_KEYWORDS)


def _should_include_entry(entry: Any) -> bool:
    """Filter RSS entries to include only Lotte-related articles."""
    title = getattr(entry, "title", "")
    summary = getattr(entry, "summary", "")
    combined = f"{title} {summary}"
    return _contains_lotte_keyword(combined)


def normalize_rss_entry(
    entry: Any,
    *,
    source_name: str,
    description_snippet_length: int = 200,
) -> NormalizedNewsItem | None:
    """Convert an RSS entry to NormalizedNewsItem."""
    title = clean_html(getattr(entry, "title", ""))
    link = getattr(entry, "link", "")

    if not title or not link:
        return None

    summary = clean_html(getattr(entry, "summary", ""))
    description_snippet = summary[:description_snippet_length]
    published_dt = _parse_rss_pubdate(entry)

    url_source = extract_source_name(link)
    final_source = url_source or source_name

    return NormalizedNewsItem(
        title=title,
        description_snippet=description_snippet,
        link=link,
        source_name=final_source,
        published_at=published_dt.isoformat(),
        published_date=published_dt.date().isoformat(),
    )


def fetch_rss_feed(
    feed_url: str, *, timeout: int = _REQUEST_TIMEOUT, verify_ssl: bool = True
) -> list[Any]:
    """Fetch and parse an RSS feed."""
    headers = {
        "User-Agent": "LotteInsightBot/1.0 (RSS aggregator; non-commercial fan project)"
    }
    response = requests.get(feed_url, headers=headers, timeout=timeout, verify=verify_ssl)
    response.raise_for_status()

    feed = feedparser.parse(response.content)
    if feed.bozo:
        logger.warning(
            "RSS feed parsing warning for %s: %s",
            feed_url,
            getattr(feed, "bozo_exception", "unknown error"),
        )

    return feed.entries


def collect_from_rss_feeds(
    feeds: list[RSSFeedConfig] | None = None,
    *,
    description_snippet_length: int = 200,
    filter_lotte: bool = True,
) -> list[tuple[NormalizedNewsItem, str]]:
    """Collect articles from multiple RSS feeds."""
    if feeds is None:
        feeds = [RSSFeedConfig(name, url, desc) for name, url, desc in RSS_FEEDS]

    all_items: list[tuple[NormalizedNewsItem, str]] = []

    for feed_config in feeds:
        try:
            logger.info(
                "Fetching RSS feed: %s (%s)", feed_config.name, feed_config.description
            )
            entries = fetch_rss_feed(feed_config.url, verify_ssl=feed_config.verify_ssl)
            logger.info("Fetched %d entries from %s", len(entries), feed_config.name)

            feed_item_count = 0
            for entry in entries:
                if filter_lotte and not _should_include_entry(entry):
                    continue

                normalized = normalize_rss_entry(
                    entry,
                    source_name=feed_config.name,
                    description_snippet_length=description_snippet_length,
                )
                if normalized:
                    all_items.append((normalized, f"rss_{feed_config.name}"))
                    feed_item_count += 1

            logger.info(
                "Collected %d Lotte-related items from %s",
                feed_item_count,
                feed_config.name,
            )

        except requests.RequestException as exc:
            logger.error(
                "Failed to fetch RSS feed %s: %s", feed_config.name, exc, exc_info=True
            )
        except ValueError as exc:
            logger.error(
                "Invalid feed payload from %s: %s", feed_config.name, exc, exc_info=True
            )

    logger.info("RSS collection completed: %d total items collected", len(all_items))
    return all_items


def run() -> int:
    """Standalone entry point for RSS collection testing."""
    logging.basicConfig(level=logging.INFO)
    logger.info("RSS collection test started")

    items = collect_from_rss_feeds()

    for item, source in items[:10]:
        print(f"[{source}] {item.title[:60]}... - {item.source_name}")

    logger.info("RSS collection test completed: %d items", len(items))
    return len(items)


if __name__ == "__main__":
    import sys

    run()
    sys.exit(0)
