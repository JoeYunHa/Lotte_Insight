"""Collect Naver News search result metadata by date range.

This is for Phase 5 training-data collection. It scrapes search result metadata
only: title, outbound URL, snippet, source, and the requested search date.

Example:
    python training/collect/collect_naver_date_range.py \
        --query "롯데 자이언츠" --start-date 2025-03-01 --end-date 2025-03-31 \
        --output training/data/raw/naver_2025_03.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

NAVER_SEARCH_URL = "https://search.naver.com/search.naver"
DEFAULT_USER_AGENT = "LotteInsightBot/1.0 (training metadata collection)"


@dataclass(frozen=True)
class SearchResult:
    title: str
    source_url: str
    description_snippet: str
    source_name: str
    search_date: str


def build_naver_date_url(*, query: str, target_date: date, start: int = 1) -> str:
    ymd = target_date.strftime("%Y%m%d")
    params = {
        "where": "news",
        "query": query,
        "sm": "tab_opt",
        "sort": "1",
        "photo": "0",
        "field": "0",
        "pd": "3",
        "ds": target_date.strftime("%Y.%m.%d"),
        "de": target_date.strftime("%Y.%m.%d"),
        "docid": "",
        "related": "0",
        "mynews": "0",
        "office_type": "0",
        "office_section_code": "0",
        "news_office_checked": "",
        "nso": f"so:r,p:from{ymd}to{ymd},a:all",
        "is_sug_officeid": "0",
        "office_category": "0",
        "service_area": "0",
        "start": str(start),
    }
    return f"{NAVER_SEARCH_URL}?{urlencode(params)}"


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _source_name(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except (TypeError, ValueError):
        return ""


def parse_search_results(html: str, *, search_date: date) -> list[SearchResult]:
    soup = BeautifulSoup(html, "lxml")
    results: list[SearchResult] = []
    for title_link in soup.select("a.news_tit"):
        title = _clean(title_link.get("title") or title_link.get_text(" ", strip=True))
        url = title_link.get("href", "").strip()
        if not title or not url:
            continue

        item = title_link.find_parent("div", class_="news_area")
        snippet = ""
        if item:
            desc = item.select_one(".news_dsc")
            snippet = _clean(desc.get_text(" ", strip=True) if desc else "")

        results.append(
            SearchResult(
                title=title,
                source_url=url,
                description_snippet=snippet,
                source_name=_source_name(url),
                search_date=search_date.isoformat(),
            )
        )
    return results


def _date_range(start_date: date, end_date: date) -> list[date]:
    days: list[date] = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def collect(
    *,
    query: str,
    start_date: date,
    end_date: date,
    pages_per_day: int,
    delay_seconds: float,
    user_agent: str,
) -> list[SearchResult]:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    rows: list[SearchResult] = []
    seen_urls: set[str] = set()

    for target_date in _date_range(start_date, end_date):
        for page_idx in range(pages_per_day):
            start = page_idx * 10 + 1
            url = build_naver_date_url(query=query, target_date=target_date, start=start)
            response = session.get(url, timeout=20)
            response.raise_for_status()
            parsed = parse_search_results(response.text, search_date=target_date)
            if not parsed:
                if page_idx == 0:
                    logger.warning(
                        "No results on first page for %s (query=%r). "
                        "Naver HTML structure may have changed.",
                        target_date.isoformat(),
                        query,
                    )
                break
            for result in parsed:
                if result.source_url in seen_urls:
                    continue
                seen_urls.add(result.source_url)
                rows.append(result)
            time.sleep(delay_seconds)

    return rows


def write_csv(rows: list[SearchResult], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "title",
                "source_url",
                "description_snippet",
                "source_name",
                "search_date",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Naver News metadata by date range.")
    parser.add_argument("--query", default="롯데 자이언츠")
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--pages-per-day", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    rows = collect(
        query=args.query,
        start_date=args.start_date,
        end_date=args.end_date,
        pages_per_day=args.pages_per_day,
        delay_seconds=args.delay_seconds,
        user_agent=args.user_agent,
    )
    write_csv(rows, args.output)
    print(f"saved: {len(rows)} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
