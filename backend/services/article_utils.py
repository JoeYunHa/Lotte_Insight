import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
import re
from urllib.parse import urlparse


@dataclass(frozen=True)
class NormalizedNewsItem:
    title: str
    description_snippet: str
    link: str
    source_name: str
    published_at: str
    published_date: str


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def extract_source_name(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication.

    Removes query parameters, fragments, and normalizes the URL structure
    to improve duplicate detection across different sources.

    Args:
        url: Raw URL string

    Returns:
        Normalized URL string

    Examples:
        >>> normalize_url("https://example.com/article?utm_source=rss#section1")
        'https://example.com/article'
        >>> normalize_url("http://www.example.com/article")
        'https://example.com/article'
    """
    try:
        url_stripped = url.strip()
        if not url_stripped:
            return ""

        parsed = urlparse(url_stripped.lower())

        # Normalize scheme to https
        scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme

        # Remove www. prefix (already lowercase from above)
        netloc = parsed.netloc.replace("www.", "")

        # Remove trailing slash from path
        path = parsed.path.rstrip("/") if parsed.path != "/" else parsed.path

        # Reconstruct URL without query params and fragments
        normalized = f"{scheme}://{netloc}{path}"
        return normalized

    except Exception:
        # Return original URL if parsing fails
        return url.strip().lower()


def parse_naver_pubdate(pub_date: str) -> datetime | None:
    try:
        return datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
    except (ValueError, TypeError):
        return None


def normalize_naver_news_item(
    item: dict,
    *,
    description_snippet_length: int,
    fallback_now: datetime | None = None,
) -> NormalizedNewsItem | None:
    title = clean_html(item.get("title", ""))
    link = item.get("originallink") or item.get("link", "")
    if not title or not link:
        return None

    parsed_dt = parse_naver_pubdate(item.get("pubDate", ""))
    published_dt = parsed_dt or fallback_now or datetime.now(timezone.utc)
    description = clean_html(item.get("description", ""))[:description_snippet_length]

    return NormalizedNewsItem(
        title=title,
        description_snippet=description,
        link=link,
        source_name=extract_source_name(link),
        published_at=published_dt.isoformat(),
        published_date=published_dt.date().isoformat(),
    )


# ---------------------------------------------------------------------------
# Shared article helpers (used by home_service, article_repository,
# report_generator to avoid duplicated JSON-parsing logic)
# ---------------------------------------------------------------------------

def parse_event_summary_json(raw: str | None) -> dict:
    """Parse the event_summary JSON blob; returns empty dict on any failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


VALID_LABEL_KEYS: frozenset[str] = frozenset({
    "INJURY_ROSTER",
    "TRANSACTION_CONTRACT",
    "MATCH_RELATED",
    "PERFORMANCE_ANALYSIS",
    "INTERVIEW",
    "CLUB_OPERATION",
    "ETC",
})


def select_primary_label_and_confidence(labels: list[dict]) -> tuple[str | None, float | None]:
    """Return (label, confidence) for the highest-confidence row."""
    if not labels:
        return None, None
    best = max(labels, key=lambda x: x.get("confidence") or 0.0)
    return best.get("label"), best.get("confidence")


def select_primary_label(labels: list[dict]) -> str | None:
    """Return the label with the highest confidence from article_labels rows."""
    label, _ = select_primary_label_and_confidence(labels)
    return label
