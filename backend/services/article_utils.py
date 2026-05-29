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
    except (AttributeError, ValueError, TypeError):
        return ""


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication.

    Only the scheme and host are lowercased — the path is preserved as-is
    because many CMS systems use case-sensitive paths (e.g. article slugs).
    Query parameters and fragments are dropped, trailing slashes stripped,
    and `www.` is removed.

    Args:
        url: Raw URL string

    Returns:
        Normalized URL string
    """
    try:
        url_stripped = url.strip()
        if not url_stripped:
            return ""

        parsed = urlparse(url_stripped)

        # Lowercase scheme & host, but preserve path case.
        scheme = parsed.scheme.lower()
        if scheme in ("http", "https"):
            scheme = "https"

        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        path = parsed.path
        # Keep root "/" but trim trailing slashes on real paths
        if path and path != "/":
            path = path.rstrip("/")

        # Reconstruct URL without query params and fragments
        if not scheme and not netloc:
            return url_stripped.rstrip("/")
        return f"{scheme}://{netloc}{path}"

    except (AttributeError, ValueError, TypeError):
        # Return original URL if parsing fails
        return url.strip()


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


LABEL_PRIORITY: list[str] = [
    "INJURY_ROSTER",
    "TRANSACTION_CONTRACT",
    "MATCH_RELATED",
    "PERFORMANCE_ANALYSIS",
    "INTERVIEW",
    "CLUB_OPERATION",
    "ETC",
]

VALID_LABEL_KEYS: frozenset[str] = frozenset(LABEL_PRIORITY)


def select_primary_label_and_confidence(labels: list[dict]) -> tuple[str | None, float | None]:
    """Return (label, confidence) for the highest-confidence row.

    Ties on confidence are broken by `LABEL_PRIORITY` (highest priority wins).
    """
    if not labels:
        return None, None
    max_conf = max((row.get("confidence") or 0.0) for row in labels)
    top = [row for row in labels if (row.get("confidence") or 0.0) == max_conf]
    if len(top) == 1:
        return top[0].get("label"), top[0].get("confidence")
    # Tiebreak by declared label priority order
    for priority_label in LABEL_PRIORITY:
        for row in top:
            if row.get("label") == priority_label:
                return priority_label, row.get("confidence")
    fallback = top[0]
    return fallback.get("label"), fallback.get("confidence")


def select_primary_label(labels: list[dict]) -> str | None:
    """Return the label with the highest confidence (priority tiebreak)."""
    label, _ = select_primary_label_and_confidence(labels)
    return label
