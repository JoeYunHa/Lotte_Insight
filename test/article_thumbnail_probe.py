"""
Batch probe for verifying whether article pages expose usable thumbnail images.

This script samples article URLs from every configured collection source
(`naver_api` and each RSS feed), attempts to extract thumbnail candidates
from the article page, downloads the best candidate, and writes a JSON report.

Usage:
    python test/article_thumbnail_probe.py
    python test/article_thumbnail_probe.py --per-source 3
    python test/article_thumbnail_probe.py --source rss_google_news_lotte
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from batch.news_collector import _fetch_news  # noqa: E402
from batch.rss_collector import (  # noqa: E402
    RSSFeedConfig,
    RSS_FEEDS,
    _should_include_entry,
    fetch_rss_feed,
    normalize_rss_entry,
)
from core.config import settings  # noqa: E402
from services.article_utils import NormalizedNewsItem, normalize_naver_news_item, normalize_url  # noqa: E402

LOGGER = logging.getLogger("article_thumbnail_probe")
REQUEST_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 20
MAX_IMAGE_BYTES = 5 * 1024 * 1024
DEFAULT_PER_SOURCE = 2
DEFAULT_OUTPUT_DIR = ROOT_DIR / "test" / "artifacts" / "article_thumbnail_probe"
IMAGE_EXTENSIONS = {
    ".jpg": ".jpg",
    ".jpeg": ".jpg",
    ".png": ".png",
    ".webp": ".webp",
    ".gif": ".gif",
}
META_SELECTORS = (
    ('meta[property="og:image"]', "content"),
    ('meta[property="og:image:url"]', "content"),
    ('meta[name="twitter:image"]', "content"),
    ('meta[name="twitter:image:src"]', "content"),
    ('link[rel="image_src"]', "href"),
)
ARTICLE_IMAGE_SELECTORS = (
    "article img",
    "[itemprop='articleBody'] img",
    ".article_view img",
    ".article-body img",
    ".newsct_article img",
    ".news_end img",
    "#articleBody img",
    "#dic_area img",
    ".content img",
    ".story-news img",
)
BAD_IMAGE_PATTERNS = (
    "logo",
    "icon",
    "sprite",
    "banner",
    "advert",
    "ads",
    "blank",
    "default",
    "profile",
    "avatar",
)
GOOGLE_NEWS_HOSTS = {"news.google.com"}
GOOGLE_PLACEHOLDER_HOSTS = {"lh3.googleusercontent.com"}


@dataclass(frozen=True)
class ProbeArticle:
    collection_source: str
    title: str
    request_url: str
    article_url: str
    source_name: str
    published_at: str
    source_homepage: str | None = None


@dataclass(frozen=True)
class ThumbnailCandidate:
    url: str
    origin: str


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._")
    return slug or "source"


def _iter_naver_articles(limit: int) -> list[ProbeArticle]:
    if not settings.naver_client_id or not settings.naver_client_secret:
        LOGGER.warning("Skipping naver_api: Naver API credentials are not configured.")
        return []

    try:
        raw_items = _fetch_news(f"{settings.team_name_ko} 자이언츠", display=max(limit * 3, 10))
    except requests.RequestException as exc:
        LOGGER.warning("Skipping naver_api: failed to fetch articles (%s)", exc)
        return []

    articles: list[ProbeArticle] = []
    seen_urls: set[str] = set()
    for item in raw_items:
        normalized = normalize_naver_news_item(
            item,
            description_snippet_length=settings.article_description_snippet_length,
        )
        if normalized is None:
            continue
        article = _to_probe_article(normalized, "naver_api")
        if not article or article.article_url in seen_urls:
            continue
        seen_urls.add(article.article_url)
        articles.append(article)
        if len(articles) >= limit:
            break
    return articles


def _iter_rss_articles(limit: int) -> list[ProbeArticle]:
    articles: list[ProbeArticle] = []
    for name, url, description in RSS_FEEDS:
        config = RSSFeedConfig(name=name, url=url, description=description)
        try:
            entries = fetch_rss_feed(config.url, verify_ssl=config.verify_ssl)
        except requests.RequestException as exc:
            LOGGER.warning("Skipping %s: failed to fetch feed (%s)", config.name, exc)
            continue

        seen_urls: set[str] = set()
        picked = 0
        for entry in entries:
            if not _should_include_entry(entry):
                continue
            normalized = normalize_rss_entry(
                entry,
                source_name=config.name,
                description_snippet_length=settings.article_description_snippet_length,
            )
            if normalized is None:
                continue
            source_homepage = None
            source_meta = getattr(entry, "source", None)
            if isinstance(source_meta, dict):
                source_homepage = source_meta.get("href")
            collection_source = f"rss_{config.name}"
            article = _to_probe_article(
                normalized,
                collection_source,
                source_homepage=source_homepage,
            )
            if not article or article.article_url in seen_urls:
                continue
            seen_urls.add(article.article_url)
            articles.append(article)
            picked += 1
            if picked >= limit:
                break
    return articles


def _to_probe_article(
    item: NormalizedNewsItem,
    collection_source: str,
    *,
    source_homepage: str | None = None,
) -> ProbeArticle | None:
    request_url = item.link.strip()
    normalized_url = normalize_url(item.link)
    if not request_url or not normalized_url:
        return None
    return ProbeArticle(
        collection_source=collection_source,
        title=item.title,
        request_url=request_url,
        article_url=normalized_url,
        source_name=item.source_name,
        published_at=item.published_at,
        source_homepage=source_homepage,
    )


def _select_sources(
    source_filter: str,
    naver_articles: list[ProbeArticle],
    rss_articles: list[ProbeArticle],
) -> list[ProbeArticle]:
    all_articles = naver_articles + rss_articles
    if source_filter == "all":
        return all_articles
    return [article for article in all_articles if article.collection_source == source_filter]


def _fetch_html(session: requests.Session, url: str) -> tuple[str, str]:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.url, response.text


def _resolve_fetch_url(article: ProbeArticle) -> str:
    return article.request_url


def _classify_error(error: str | None) -> str | None:
    if not error:
        return None
    lowered = error.lower()
    if "placeholder image" in lowered or "original article unresolved" in lowered:
        return "google_intermediary"
    if "404" in lowered:
        return "http_404"
    if "403" in lowered:
        return "http_403"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "no image candidate found" in lowered:
        return "no_candidate"
    if "non-image content-type" in lowered:
        return "non_image"
    if "image too large" in lowered:
        return "image_too_large"
    return "other"


def _extract_candidates(article_url: str, html: str) -> list[ThumbnailCandidate]:
    soup = BeautifulSoup(html, "lxml")
    candidates: list[ThumbnailCandidate] = []
    seen: set[str] = set()

    def add_candidate(raw_url: str | None, origin: str) -> None:
        if not raw_url:
            return
        resolved = urljoin(article_url, raw_url.strip())
        parsed = urlparse(resolved)
        if parsed.scheme not in {"http", "https"}:
            return
        normalized = resolved
        lowered = normalized.lower()
        if any(pattern in lowered for pattern in BAD_IMAGE_PATTERNS):
            return
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(ThumbnailCandidate(url=normalized, origin=origin))

    for selector, attr in META_SELECTORS:
        for node in soup.select(selector):
            add_candidate(node.get(attr), f"meta:{selector}")

    for selector in ARTICLE_IMAGE_SELECTORS:
        for node in soup.select(selector):
            add_candidate(
                node.get("data-src")
                or node.get("data-original")
                or node.get("src"),
                f"body:{selector}",
            )

    return candidates


def _file_extension_from_url(url: str, content_type: str | None) -> str:
    path_ext = Path(urlparse(url).path).suffix.lower()
    if path_ext in IMAGE_EXTENSIONS:
        return IMAGE_EXTENSIONS[path_ext]
    if content_type:
        content_type = content_type.lower()
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"
        if "gif" in content_type:
            return ".gif"
    return ".jpg"


def _is_google_placeholder(
    resolved_article_url: str,
    candidate: ThumbnailCandidate,
) -> bool:
    article_host = urlparse(resolved_article_url).netloc.lower()
    candidate_host = urlparse(candidate.url).netloc.lower()
    return (
        article_host in GOOGLE_NEWS_HOSTS
        and candidate_host in GOOGLE_PLACEHOLDER_HOSTS
        and candidate.origin.startswith("meta:")
    )


def _download_candidate(
    session: requests.Session,
    candidate: ThumbnailCandidate,
    output_dir: Path,
    file_stem: str,
) -> dict:
    response = session.get(candidate.url, timeout=DOWNLOAD_TIMEOUT, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "image" not in content_type.lower():
        raise ValueError(f"non-image content-type: {content_type or 'unknown'}")

    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_IMAGE_BYTES:
        raise ValueError(f"image too large: {content_length} bytes")

    data = response.content
    if not data:
        raise ValueError("empty image body")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"image too large after download: {len(data)} bytes")

    output_dir.mkdir(parents=True, exist_ok=True)
    ext = _file_extension_from_url(candidate.url, content_type)
    file_path = output_dir / f"{file_stem}{ext}"
    file_path.write_bytes(data)

    return {
        "thumbnail_url": candidate.url,
        "thumbnail_origin": candidate.origin,
        "thumbnail_content_type": content_type,
        "thumbnail_size_bytes": len(data),
        "saved_path": str(file_path.relative_to(ROOT_DIR)),
    }


def _probe_article(
    session: requests.Session,
    article: ProbeArticle,
    output_dir: Path,
    index: int,
) -> dict:
    result = asdict(article)
    result["status"] = "failed"
    result["resolved_article_url"] = None
    result["thumbnail_url"] = None
    result["thumbnail_origin"] = None
    result["thumbnail_content_type"] = None
    result["thumbnail_size_bytes"] = None
    result["saved_path"] = None
    result["candidate_count"] = 0
    result["error"] = None
    result["failure_reason"] = None

    try:
        fetch_url = _resolve_fetch_url(article)
        resolved_url, html = _fetch_html(session, fetch_url)
        result["resolved_article_url"] = resolved_url
        candidates = _extract_candidates(resolved_url, html)
        result["candidate_count"] = len(candidates)
        if not candidates:
            result["error"] = "no image candidate found"
            result["failure_reason"] = _classify_error(result["error"])
            return result

        file_stem = f"{index:03d}_{_safe_slug(article.collection_source)}"
        for candidate in candidates:
            try:
                if _is_google_placeholder(resolved_url, candidate):
                    result["error"] = "google news placeholder image; original article unresolved"
                    continue
                downloaded = _download_candidate(session, candidate, output_dir, file_stem)
            except Exception as exc:  # noqa: BLE001
                result["error"] = str(exc)
                continue
            result.update(downloaded)
            result["status"] = "success"
            result["error"] = None
            result["failure_reason"] = None
            return result

        if result["error"] is None:
            result["error"] = "all image candidates failed"
        result["failure_reason"] = _classify_error(result["error"])
        return result
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        result["failure_reason"] = _classify_error(result["error"])
        return result


def _build_summary(results: Iterable[dict]) -> dict:
    result_list = list(results)
    by_source: dict[str, dict] = {}
    failure_reasons: dict[str, int] = {}
    for row in result_list:
        source = row["collection_source"]
        bucket = by_source.setdefault(
            source,
            {"articles": 0, "successes": 0, "failures": 0},
        )
        bucket["articles"] += 1
        if row["status"] == "success":
            bucket["successes"] += 1
        else:
            bucket["failures"] += 1
            reason = row.get("failure_reason") or "other"
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

    return {
        "total_articles": len(result_list),
        "successes": sum(1 for row in result_list if row["status"] == "success"),
        "failures": sum(1 for row in result_list if row["status"] != "success"),
        "sources": by_source,
        "failure_reasons": failure_reasons,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe article pages and download thumbnail candidates by source."
    )
    parser.add_argument("--per-source", type=int, default=DEFAULT_PER_SOURCE)
    parser.add_argument("--source", default="all")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    output_dir = Path(args.output_dir)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        }
    )

    naver_articles = _iter_naver_articles(args.per_source)
    rss_articles = _iter_rss_articles(args.per_source)
    targets = _select_sources(args.source, naver_articles, rss_articles)

    if not targets:
        LOGGER.error("No probe targets found for source=%s", args.source)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for index, article in enumerate(targets, start=1):
        LOGGER.info("Probing [%s] %s", article.collection_source, article.request_url)
        results.append(_probe_article(session, article, output_dir, index))

    summary = _build_summary(results)
    report = {
        "generated_at": datetime.now().isoformat(),
        "per_source": args.per_source,
        "selected_source": args.source,
        "summary": summary,
        "results": results,
    }

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {report_path.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
