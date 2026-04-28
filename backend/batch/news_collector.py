"""
네이버 뉴스 검색 API로 롯데 자이언츠 관련 기사 메타데이터 수집.
- description은 분류 보조 입력으로만 사용, DB에 저장하지 않음.
- URL 기준 upsert로 중복 방지.
"""

import re
import logging
import requests
from datetime import datetime
from urllib.parse import urlparse

from core.config import settings
from core.database import supabase
from models.classifier import classify
from models.player_extractor import extract_players

logger = logging.getLogger(__name__)

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
BASE_KEYWORDS = ["롯데 자이언츠"]


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
    resp = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("items", [])


def _get_player_names() -> list[str]:
    result = supabase.table("players").select("name, name_variants").execute()
    names: list[str] = []
    for row in result.data:
        names.append(row["name"])
        if row.get("name_variants"):
            names.extend(row["name_variants"])
    return names


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
            published_at = datetime.utcnow().isoformat()

        rows.append({
            "source_url": link,
            "source_name": _source_name(link),
            "title": title,
            "published_at": published_at,
        })

    if not rows:
        return 0

    result = supabase.table("articles").upsert(rows, on_conflict="source_url").execute()
    return len(result.data)


def _label_and_link_players(items: list[dict]):
    """분류 + 선수 매칭 후 저장. description은 분류 보조 입력용으로만 사용."""
    for item in items:
        title = _clean_html(item.get("title", ""))
        description = _clean_html(item.get("description", ""))[:120]
        link = item.get("originallink") or item.get("link", "")
        if not link:
            continue

        result = supabase.table("articles").select("id").eq("source_url", link).limit(1).execute()
        if not result.data:
            continue
        article_id = result.data[0]["id"]

        label_result = classify(title, description)
        supabase.table("article_labels").upsert(
            {
                "article_id": article_id,
                "label": label_result["label"],
                "confidence": label_result["confidence"],
            },
            on_conflict="article_id",
        ).execute()

        player_ids = extract_players(title)
        if player_ids:
            player_rows = [{"article_id": article_id, "player_id": pid} for pid in player_ids]
            supabase.table("article_players").upsert(
                player_rows, on_conflict="article_id,player_id"
            ).execute()


def run() -> int:
    logger.info("뉴스 수집 시작")

    player_names = _get_player_names()
    keywords = BASE_KEYWORDS + [f"롯데 {name}" for name in player_names[:20]]

    all_items: list[dict] = []
    for keyword in keywords:
        try:
            items = _fetch_news(keyword)
            all_items.extend(items)
            logger.info(f"'{keyword}': {len(items)}건 수집")
        except Exception as e:
            logger.error(f"'{keyword}' 수집 실패: {e}")

    # URL 기준 중복 제거
    seen: set[str] = set()
    unique_items: list[dict] = []
    for item in all_items:
        url = item.get("originallink") or item.get("link", "")
        if url and url not in seen:
            seen.add(url)
            unique_items.append(item)

    _upsert_articles(unique_items)
    _label_and_link_players(unique_items)

    logger.info(f"뉴스 수집 완료: {len(unique_items)}건 처리")
    return len(unique_items)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    count = run()
    print(f"처리 완료: {count}건")
    sys.exit(0)
