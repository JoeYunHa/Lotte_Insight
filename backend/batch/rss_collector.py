"""
Collect Lotte Giants news articles from RSS feeds.

This module provides an alternative/supplementary data source to the Naver Search API.
RSS feeds are free, require no API keys, and provide good coverage of Korean sports news.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from calendar import timegm
from typing import Any

import feedparser
import requests
import urllib3

# Disable SSL warnings for feeds with certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from services.article_utils import NormalizedNewsItem, clean_html, extract_source_name

logger = logging.getLogger(__name__)

# RSS feed sources
# Format: (name, url, description)
RSS_FEEDS = [
    # Phase 1 - Core feeds
    (
        "google_news_lotte",
        "https://news.google.com/rss/search?q=롯데+자이언츠&hl=ko&gl=KR&ceid=KR:ko",
        "Google News - 롯데 자이언츠 키워드 검색",
    ),
    (
        "google_news_kbo",
        "https://news.google.com/rss/search?q=KBO+롯데&hl=ko&gl=KR&ceid=KR:ko",
        "Google News - KBO 롯데 키워드 검색",
    ),
    (
        "donga_sports",
        "http://rss.donga.com/sports.xml",
        "동아일보 - 스포츠",
    ),
    # Phase 2 - Successfully recovered feeds (2026-05-26)
    (
        "khan_baseball",
        "https://sports.khan.co.kr/rss/baseball",
        "스포츠경향 - 야구 전문",
    ),
    (
        "yonhap_sports",
        "https://www.yna.co.kr/rss/sports.xml",
        "연합뉴스 - 스포츠",
    ),
    # Phase 2 - Permanently disabled (RSS service discontinued)
    # (
    #     "sportsworld_baseball",
    #     "http://rss.sportsworldi.com/sw_baseball.xml",
    #     "스포츠월드 - 야구",  # Server unreachable
    # ),
    # (
    #     "joins_sports",
    #     "http://rss.joinsmsn.com/joins_sports_list.xml",
    #     "중앙일보 - 스포츠",  # RSS service discontinued (returns HTML)
    # ),
    # (
    #     "mbc_sports",
    #     "http://imnews.imbc.com/rss/news/news_07.xml",
    #     "MBC - 스포츠",  # RSS service discontinued (returns HTML)
    # ),
]

# Keywords to filter Lotte-related articles
LOTTE_KEYWORDS = [
    "롯데",
    "lotte",
    "자이언츠",
    "giants",
    "사직",
    "sajik",
]

_REQUEST_TIMEOUT = 10


@dataclass(frozen=True)
class RSSFeedConfig:
    """Configuration for an RSS feed source."""

    name: str
    url: str
    description: str


def _parse_rss_pubdate(entry: Any) -> datetime:
    """Parse publication date from RSS entry.

    RSS feeds may use different date formats. feedparser normalizes them
    to time.struct_time in the published_parsed or updated_parsed field.
    """
    # Try published_parsed first, then updated_parsed
    time_struct = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )

    if time_struct:
        try:
            # feedparser returns UTC-like struct_time; use timegm to avoid local-time skew.
            timestamp = timegm(time_struct)
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            pass

    # Fallback to current time
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
    """Convert an RSS entry to NormalizedNewsItem.

    Args:
        entry: feedparser entry object
        source_name: Name of the RSS feed source
        description_snippet_length: Max length of description snippet

    Returns:
        NormalizedNewsItem or None if entry is invalid
    """
    title = clean_html(getattr(entry, "title", ""))
    link = getattr(entry, "link", "")

    if not title or not link:
        return None

    # Get description/summary
    summary = clean_html(getattr(entry, "summary", ""))
    description_snippet = summary[:description_snippet_length]

    # Parse publication date
    published_dt = _parse_rss_pubdate(entry)

    # Extract source from URL if not already set
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
    feed_url: str, *, timeout: int = _REQUEST_TIMEOUT
) -> list[Any]:
    """Fetch and parse an RSS feed.

    Args:
        feed_url: URL of the RSS feed
        timeout: Request timeout in seconds

    Returns:
        List of feed entries

    Raises:
        requests.RequestException: If feed fetch fails
    """
    # Fetch feed content with explicit User-Agent
    headers = {
        "User-Agent": "LotteInsightBot/1.0 (RSS aggregator; non-commercial fan project)"
    }
    # Disable SSL verification for feeds with certificate issues (e.g., Yonhap News)
    response = requests.get(feed_url, headers=headers, timeout=timeout, verify=False)
    response.raise_for_status()

    # Parse with feedparser
    feed = feedparser.parse(response.content)

    if feed.bozo:
        # Parsing encountered an error, but may still have partial data
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
    """Collect articles from multiple RSS feeds.

    Args:
        feeds: List of RSS feed configurations. If None, uses default RSS_FEEDS.
        description_snippet_length: Max length of description snippet
        filter_lotte: If True, only include Lotte-related articles

    Returns:
        List of (NormalizedNewsItem, collection_source) tuples
    """
    if feeds is None:
        feeds = [RSSFeedConfig(name, url, desc) for name, url, desc in RSS_FEEDS]

    all_items: list[tuple[NormalizedNewsItem, str]] = []

    for feed_config in feeds:
        try:
            logger.info(
                "Fetching RSS feed: %s (%s)", feed_config.name, feed_config.description
            )
            entries = fetch_rss_feed(feed_config.url)
            logger.info("Fetched %d entries from %s", len(entries), feed_config.name)

            # Filter and normalize entries
            for entry in entries:
                # Skip non-Lotte articles if filtering is enabled
                if filter_lotte and not _should_include_entry(entry):
                    continue

                normalized = normalize_rss_entry(
                    entry,
                    source_name=feed_config.name,
                    description_snippet_length=description_snippet_length,
                )
                if normalized:
                    all_items.append((normalized, f"rss_{feed_config.name}"))

            logger.info(
                "Collected %d Lotte-related items from %s",
                sum(1 for item, _ in all_items if item.source_name == feed_config.name),
                feed_config.name,
            )

        except requests.RequestException as exc:
            logger.error(
                "Failed to fetch RSS feed %s: %s", feed_config.name, exc, exc_info=True
            )
        except Exception as exc:
            logger.error(
                "Unexpected error processing RSS feed %s: %s",
                feed_config.name,
                exc,
                exc_info=True,
            )

    logger.info("RSS collection completed: %d total items collected", len(all_items))
    return all_items


def run() -> int:
    """Standalone entry point for RSS collection testing.

    Returns:
        Number of items collected
    """
    logging.basicConfig(level=logging.INFO)
    logger.info("RSS collection test started")

    items = collect_from_rss_feeds()

    for item, source in items[:10]:  # Print first 10 for inspection
        print(f"[{source}] {item.title[:60]}... - {item.source_name}")

    logger.info("RSS collection test completed: %d items", len(items))
    return len(items)


if __name__ == "__main__":
    import sys

    count = run()
    sys.exit(0)
