"""
Collect Lotte Giants news articles from the Naver Search API.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from core.config import settings
from core.database import supabase
from batch.gpt_summarizer import gpt_summarize_batch
from models.classifier import classify_batch
from models.lotte_related_detector import detect_is_lotte_related_batch
from models.player_extractor import extract_players
from models.stance_classifier import classify_stance_batch
from services.article_utils import NormalizedNewsItem, normalize_naver_news_item
from services.player_catalog import list_player_names

_FETCH_WORKERS = 8

logger = logging.getLogger(__name__)

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
BASE_KEYWORDS = [f"{settings.team_name_ko} 자이언츠"]


def _fetch_news(keyword: str, display: int = 100) -> list[dict]:
    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
    }
    params = {"query": keyword, "display": display, "sort": "date"}
    response = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    return response.json().get("items", [])


def _normalized_items(items: list[dict]) -> list[NormalizedNewsItem]:
    normalized_items: list[NormalizedNewsItem] = []
    for item in items:
        normalized = normalize_naver_news_item(
            item,
            description_snippet_length=settings.article_description_snippet_length,
        )
        if normalized is not None:
            normalized_items.append(normalized)
    return normalized_items


def _should_gpt_summarize(label_result: dict) -> bool:
    summarizable = set(settings.gpt_summary_labels)
    if label_result["label"] in summarizable:
        return True
    return any(s in summarizable for s in label_result.get("secondary_labels", []))


def _run_inference(items: list[NormalizedNewsItem]) -> list[dict]:
    """
    Pipeline:
      1. is_lotte_related gate (hybrid: rule + KoELECTRA)
      2. label classification  (KoELECTRA multi-label, lotte-related only)
      3. stance classification (KoELECTRA 3-class, lotte-related only)
      4. GPT event_summary     (gpt-4o-mini, lotte-related + summarizable labels only)
    """
    total = len(items)
    logger.info("Inference started: %d items", total)

    articles = [{"title": item.title, "description_snippet": item.description_snippet} for item in items]

    # Step 1: is_lotte_related
    lr_results = detect_is_lotte_related_batch(articles)
    lotte_indices = [i for i, lr in enumerate(lr_results) if lr["is_lotte_related"]]
    logger.info("is_lotte_related: %d/%d items", len(lotte_indices), total)

    related_articles = [articles[i] for i in lotte_indices]

    # Step 2: label classification (lotte-related only)
    related_label_results = classify_batch(related_articles) if related_articles else []
    logger.info("Classification done: %d items", len(related_articles))

    label_results = [{"label": "ETC", "confidence": 0.0, "secondary_labels": []} for _ in items]
    for idx, label_result in zip(lotte_indices, related_label_results):
        label_results[idx] = label_result

    # Step 3: stance classification (lotte-related only)
    stance_results_related = classify_stance_batch(related_articles) if related_articles else []
    stance_results = [{"label": None, "confidence": 0.0, "source": "not_applicable"} for _ in items]
    for idx, stance in zip(lotte_indices, stance_results_related):
        stance_results[idx] = stance
    logger.info("Stance classification done: %d items", len(related_articles))

    # Step 4: GPT event_summary (lotte-related + summarizable labels only)
    gpt_indices = [
        i for i in lotte_indices
        if _should_gpt_summarize(label_results[i])
    ]
    gpt_inputs = [articles[i] for i in gpt_indices]
    gpt_results_list = gpt_summarize_batch(gpt_inputs) if gpt_inputs else []
    gpt_results = [{} for _ in items]
    for idx, gpt_result in zip(gpt_indices, gpt_results_list):
        gpt_results[idx] = gpt_result
    logger.info("GPT summarization done: %d items", len(gpt_indices))

    enriched = []
    for i, (item, label_result, lr_result) in enumerate(zip(items, label_results, lr_results)):
        stance = stance_results[i]
        gpt = gpt_results[i]
        if lr_result["is_lotte_related"]:
            event_summary_json = json.dumps(
                {
                    "is_lotte_related": True,
                    "is_lotte_related_confidence": lr_result["confidence"],
                    "is_lotte_related_source": lr_result["source"],
                    "lotte_stance": stance["label"],
                    "lotte_stance_confidence": stance["confidence"],
                    "lotte_stance_source": stance["source"],
                    "event_summary": gpt.get("event_summary", ""),
                    "key_players": gpt.get("key_players", []),
                    "summary_source": gpt.get("source", "not_applicable"),
                },
                ensure_ascii=False,
            )
        else:
            event_summary_json = json.dumps(
                {
                    "is_lotte_related": False,
                    "is_lotte_related_confidence": lr_result["confidence"],
                    "is_lotte_related_source": lr_result["source"],
                    "lotte_stance": None,
                    "lotte_stance_confidence": None,
                    "lotte_stance_source": "not_applicable",
                    "event_summary": "",
                    "key_players": [],
                    "summary_source": "not_applicable",
                },
                ensure_ascii=False,
            )
        enriched.append({
            "item": item,
            "label_result": label_result,
            "is_lotte_related": lr_result["is_lotte_related"],
            "event_summary_json": event_summary_json,
        })
    return enriched


def _upsert_articles(enriched: list[dict]) -> int:
    rows = []
    for e in enriched:
        rows.append({
            "source_url": e["item"].link,
            "source_name": e["item"].source_name,
            "title": e["item"].title,
            "published_at": e["item"].published_at,
            "event_summary": e["event_summary_json"],
        })
    if not rows:
        return 0
    result = supabase.table("articles").upsert(rows, on_conflict="source_url").execute()
    saved = len(result.data)
    logger.info("Upserted %d articles to DB", saved)
    return saved


_ID_MAP_CHUNK_SIZE = 100


def _get_article_id_map(enriched: list[dict]) -> dict[str, int]:
    urls = [e["item"].link for e in enriched]
    if not urls:
        return {}
    id_map: dict[str, int] = {}
    for i in range(0, len(urls), _ID_MAP_CHUNK_SIZE):
        chunk = urls[i : i + _ID_MAP_CHUNK_SIZE]
        result = (
            supabase.table("articles")
            .select("id, source_url")
            .in_("source_url", chunk)
            .execute()
        )
        for row in result.data:
            id_map[row["source_url"]] = row["id"]
    return id_map


def _save_labels_and_players(enriched: list[dict], id_map: dict[str, int]) -> None:
    label_rows: list[dict] = []
    player_rows: list[dict] = []

    for e in enriched:
        if not e["is_lotte_related"]:
            continue
        item = e["item"]
        article_id = id_map.get(item.link)
        if not article_id:
            continue

        label_result = e["label_result"]
        label_rows.append({
            "article_id": article_id,
            "label": label_result["label"],
            "confidence": label_result["confidence"],
        })
        for secondary in label_result.get("secondary_labels", []):
            label_rows.append(
                {"article_id": article_id, "label": secondary, "confidence": None}
            )

        for player_id in extract_players(item.title):
            player_rows.append({"article_id": article_id, "player_id": player_id})

    if label_rows:
        supabase.table("article_labels").upsert(
            label_rows, on_conflict="article_id,label"
        ).execute()
        logger.info("Upserted %d label rows", len(label_rows))

    if player_rows:
        supabase.table("article_players").upsert(
            player_rows, on_conflict="article_id,player_id"
        ).execute()
        logger.info("Upserted %d player-article rows", len(player_rows))


def run() -> int:
    from datetime import datetime, timezone, timedelta
    from batch import game_collector

    _KST = timezone(timedelta(hours=9))

    logger.info("News collection started")

    keywords = BASE_KEYWORDS + [
        f"{settings.team_name_ko} {name}"
        for name in list_player_names(active_only=True)[: settings.article_keyword_limit]
    ]

    all_items: list[dict] = []
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as executor:
        future_to_keyword = {executor.submit(_fetch_news, kw): kw for kw in keywords}
        for future in as_completed(future_to_keyword):
            keyword = future_to_keyword[future]
            try:
                items = future.result()
                all_items.extend(items)
                logger.info("Collected %d items for keyword '%s'", len(items), keyword)
            except Exception as exc:
                logger.error("Failed to collect keyword '%s': %s", keyword, exc)

    seen: set[str] = set()
    unique_items: list[dict] = []
    for item in all_items:
        url = item.get("originallink") or item.get("link", "")
        if url and url not in seen:
            seen.add(url)
            unique_items.append(item)
    logger.info("Dedup: %d raw → %d unique", len(all_items), len(unique_items))

    normalized_items = _normalized_items(unique_items)
    logger.info("Normalized: %d items (dropped %d)", len(normalized_items), len(unique_items) - len(normalized_items))
    enriched = _run_inference(normalized_items)
    _upsert_articles(enriched)
    id_map = _get_article_id_map(enriched)
    _save_labels_and_players(enriched, id_map)

    today_kst = datetime.now(_KST).date()
    try:
        game_collector.sync_game(today_kst)
    except Exception as exc:
        logger.warning("경기 데이터 동기화 실패 (무시): %s", exc)

    logger.info("News collection completed: %s items", len(unique_items))
    return len(unique_items)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    count = run()
    print(f"Processed articles: {count}")
    sys.exit(0)
