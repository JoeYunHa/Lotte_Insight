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


def is_past_date(target_date: date) -> bool:
    return target_date < date.today()
