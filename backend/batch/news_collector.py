"""
Collect Lotte Giants news articles from the Naver Search API.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

import requests
from requests import RequestException

from batch.gpt_summarizer import gpt_classify_labels_batch, gpt_summarize_batch
from batch.parallel_utils import run_indexed_parallel
from batch.rss_collector import collect_from_rss_feeds
from core.config import settings
from core.database import supabase
from models.lotte_related_detector import detect_is_lotte_related_batch
from models.player_stance_classifier import classify_player_stance_batch
from models.stance_classifier import classify_stance_batch
from services.article_utils import NormalizedNewsItem, normalize_naver_news_item, normalize_url
from services.player_catalog import (
    PlayerAliasIndex,
    build_player_alias_index,
    get_active_player_ids,
    list_player_canonical_names,
)

_FETCH_WORKERS = 8
_ID_MAP_CHUNK_SIZE = 100

logger = logging.getLogger(__name__)
NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"


def _build_event_summary_json(
    *,
    is_lotte_related: bool,
    lr_result: dict,
    stance: dict,
    gpt: dict,
) -> str:
    payload = {
        "is_lotte_related": is_lotte_related,
        "is_lotte_related_confidence": lr_result["confidence"],
        "is_lotte_related_source": lr_result["source"],
        "team_stance": stance["label"] if is_lotte_related else None,
        "team_stance_confidence": stance["confidence"] if is_lotte_related else None,
        "team_stance_source": stance["source"] if is_lotte_related else "not_applicable",
        "event_summary": gpt.get("event_summary", "") if is_lotte_related else "",
        "key_players": gpt.get("key_players", []) if is_lotte_related else [],
        "summary_source": gpt.get("source", "not_applicable") if is_lotte_related else "not_applicable",
    }
    return json.dumps(payload, ensure_ascii=False)


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


def _normalize_with_source(
    naver_items: list[dict],
    rss_items_with_source: list[tuple[NormalizedNewsItem, str]],
) -> list[tuple[NormalizedNewsItem, str]]:
    all_normalized: list[tuple[NormalizedNewsItem, str]] = []
    for item in _normalized_items(naver_items):
        all_normalized.append((item, "naver_api"))
    all_normalized.extend(rss_items_with_source)
    return all_normalized


def _should_gpt_summarize(label_result: dict) -> bool:
    summarizable = set(settings.gpt_summary_labels)
    if label_result["label"] in summarizable:
        return True
    return any(s in summarizable for s in label_result.get("secondary_labels", []))


def _parse_published_at(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_recent_item(item: NormalizedNewsItem, *, now: datetime | None = None) -> bool:
    published_at = _parse_published_at(item.published_at)
    if published_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current - timedelta(days=settings.article_recent_days)
    return cutoff <= published_at <= current + timedelta(days=1)


def _filter_recent_items(
    items: list[tuple[NormalizedNewsItem, str, str]],
    *,
    now: datetime | None = None,
) -> list[tuple[NormalizedNewsItem, str, str]]:
    return [item_tuple for item_tuple in items if _is_recent_item(item_tuple[0], now=now)]


def _is_current_roster_item(
    item: NormalizedNewsItem,
    alias_index: PlayerAliasIndex,
    active_ids: frozenset[str],
) -> bool:
    """Return True unless the title matches only inactive players.

    Articles with no player match (general team news) are always kept.
    Articles mentioning at least one active player are kept.
    Articles that only match inactive players (e.g. released foreign players) are dropped.
    """
    matched = alias_index.match_player_ids(item.title)
    if not matched:
        return True
    return any(pid in active_ids for pid in matched)


def _filter_current_roster_items(
    items: list[tuple[NormalizedNewsItem, str, str]],
    alias_index: PlayerAliasIndex,
    active_ids: frozenset[str],
) -> list[tuple[NormalizedNewsItem, str, str]]:
    return [t for t in items if _is_current_roster_item(t[0], alias_index, active_ids)]


def _run_inference(items: list[NormalizedNewsItem], alias_index: PlayerAliasIndex) -> list[dict]:
    total = len(items)
    logger.info("Inference started: %d items", total)

    articles = [{"title": item.title, "description_snippet": item.description_snippet} for item in items]

    lr_results = detect_is_lotte_related_batch(articles)
    lotte_indices = [i for i, lr in enumerate(lr_results) if lr["is_lotte_related"]]
    logger.info("is_lotte_related: %d/%d items", len(lotte_indices), total)

    related_articles = [articles[i] for i in lotte_indices]
    related_label_results = gpt_classify_labels_batch(related_articles) if related_articles else []
    logger.info("Classification done: %d items", len(related_articles))

    label_results: list[dict] = [
        {"label": "ETC", "confidence": 0.0, "secondary_labels": []} for _ in items
    ]
    for idx, label_result in zip(lotte_indices, related_label_results):
        label_results[idx] = label_result

    stance_results_related = classify_stance_batch(related_articles) if related_articles else []
    stance_results: list[dict] = [
        {"label": None, "confidence": 0.0, "source": "not_applicable"} for _ in items
    ]
    for idx, stance in zip(lotte_indices, stance_results_related):
        stance_results[idx] = stance
    logger.info("Stance classification done: %d items", len(related_articles))

    gpt_indices = [i for i in lotte_indices if _should_gpt_summarize(label_results[i])]
    gpt_inputs = [articles[i] for i in gpt_indices]
    gpt_results_list = gpt_summarize_batch(gpt_inputs) if gpt_inputs else []
    gpt_results: list[dict] = [{} for _ in items]
    for idx, gpt_result in zip(gpt_indices, gpt_results_list):
        gpt_results[idx] = gpt_result
    logger.info("GPT summarization done: %d items", len(gpt_indices))

    id_to_name: dict[str, str] = {
        pid: aliases[0]
        for pid, aliases in alias_index.aliases_by_player_id.items()
        if aliases
    }

    ps_meta: list[tuple[int, str]] = []
    ps_inputs: list[dict] = []
    detected_players: list[list[str]] = [[] for _ in items]

    for i in lotte_indices:
        item = items[i]
        player_ids = alias_index.match_player_ids(item.title)
        detected_players[i] = player_ids
        for pid in player_ids:
            ps_meta.append((i, pid))
            ps_inputs.append(
                {
                    "title": item.title,
                    "description_snippet": item.description_snippet,
                    "player_name": id_to_name.get(pid, ""),
                }
            )

    ps_raw = classify_player_stance_batch(ps_inputs) if ps_inputs else []
    player_stances: list[dict[str, dict]] = [{} for _ in items]
    for (i, pid), stance_result in zip(ps_meta, ps_raw):
        player_stances[i][pid] = stance_result
    logger.info("Player stance classification done: %d player-article pairs", len(ps_inputs))

    enriched: list[dict] = []
    for i, (item, label_result, lr_result) in enumerate(zip(items, label_results, lr_results)):
        stance = stance_results[i]
        gpt = gpt_results[i]
        event_summary_json = _build_event_summary_json(
            is_lotte_related=lr_result["is_lotte_related"],
            lr_result=lr_result,
            stance=stance,
            gpt=gpt,
        )
        enriched.append(
            {
                "item": item,
                "label_result": label_result,
                "is_lotte_related": lr_result["is_lotte_related"],
                "event_summary_json": event_summary_json,
                "detected_player_ids": detected_players[i],
                "player_stances": player_stances[i],
            }
        )
    return enriched


def _upsert_articles(enriched: list[dict]) -> tuple[int, dict[str, int]]:
    rows = [
        {
            "source_url": e["normalized_url"],
            "source_name": e["item"].source_name,
            "title": e["item"].title,
            "published_at": e["item"].published_at,
            "event_summary": e["event_summary_json"],
            "collection_source": e.get("collection_source", "naver_api"),
        }
        for e in enriched
    ]
    if not rows:
        return 0, {}

    result = supabase.table("articles").upsert(rows, on_conflict="source_url").execute()
    saved = len(result.data)
    logger.info("Upserted %d articles to DB", saved)

    id_map: dict[str, int] = {}
    for row in result.data or []:
        row_id = row.get("id")
        row_url = row.get("source_url")
        if isinstance(row_id, int) and isinstance(row_url, str):
            id_map[row_url] = row_id

    return saved, id_map


def _get_article_id_map(enriched: list[dict]) -> dict[str, int]:
    urls = sorted({e["normalized_url"] for e in enriched})
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
        article_id = id_map.get(e["normalized_url"])
        if not article_id:
            continue

        label_result = e["label_result"]
        if label_result.get("source") == "gpt_error":
            continue
        label_rows.append(
            {
                "article_id": article_id,
                "label": label_result["label"],
                "confidence": label_result["confidence"],
            }
        )
        for secondary in label_result.get("secondary_labels", []):
            label_rows.append({"article_id": article_id, "label": secondary, "confidence": None})

        ps_map = e.get("player_stances", {})
        for player_id in e.get("detected_player_ids", []):
            stance = ps_map.get(player_id, {})
            row: dict = {"article_id": article_id, "player_id": int(player_id)}
            label = stance.get("label")
            if label is not None:
                row["player_stance"] = label
            player_rows.append(row)

    if label_rows:
        supabase.table("article_labels").upsert(label_rows, on_conflict="article_id,label").execute()
        logger.info("Upserted %d label rows", len(label_rows))

    if player_rows:
        supabase.table("article_players").upsert(player_rows, on_conflict="article_id,player_id").execute()
        logger.info("Upserted %d player-article rows", len(player_rows))


def _query_existing_urls(urls: list[str]) -> set[str]:
    """Return the subset of URLs already present in the articles table."""
    existing: set[str] = set()
    for i in range(0, len(urls), _ID_MAP_CHUNK_SIZE):
        chunk = urls[i : i + _ID_MAP_CHUNK_SIZE]
        result = supabase.table("articles").select("source_url").in_("source_url", chunk).execute()
        for row in result.data or []:
            existing.add(row["source_url"])
    return existing


def run() -> int:
    from batch import game_collector
    from core.time_utils import today_kst

    logger.info("News collection started")

    base_keywords = [f"{settings.team_name_ko} 자이언츠"]
    keywords = base_keywords + [
        f"{settings.team_name_ko} {name}"
        for name in list_player_canonical_names(active_only=True)[: settings.article_keyword_limit]
    ]

    def _on_keyword_error(idx: int, exc: Exception) -> list[dict]:
        keyword = keywords[idx]
        if isinstance(exc, RequestException):
            logger.error("Request failed for keyword '%s': %s", keyword, exc)
        elif isinstance(exc, ValueError):
            logger.error("Invalid response for keyword '%s': %s", keyword, exc)
        elif isinstance(exc, RuntimeError):
            logger.error("Runtime failure for keyword '%s': %s", keyword, exc)
        elif isinstance(exc, KeyError):
            logger.error("Response shape error for keyword '%s': %s", keyword, exc)
        else:
            logger.error("Unexpected keyword failure for '%s': %s", keyword, exc)
        return []

    keyword_items = run_indexed_parallel(
        keywords,
        _fetch_news,
        max_workers=_FETCH_WORKERS,
        on_error=_on_keyword_error,
    )

    naver_items: list[dict] = []
    for keyword, items in zip(keywords, keyword_items):
        naver_items.extend(items)
        logger.info("Collected %d items for keyword '%s'", len(items), keyword)

    logger.info("Naver API collection: %d raw items", len(naver_items))

    rss_items_with_source = collect_from_rss_feeds(
        description_snippet_length=settings.article_description_snippet_length
    )
    logger.info("RSS collection: %d items from all feeds", len(rss_items_with_source))

    all_normalized = _normalize_with_source(naver_items, rss_items_with_source)
    logger.info(
        "Total items before dedup: %d (Naver: %d, RSS: %d)",
        len(all_normalized),
        len(naver_items),
        len(rss_items_with_source),
    )

    seen_urls: set[str] = set()
    unique_items_with_source: list[tuple[NormalizedNewsItem, str, str]] = []
    for item, source in all_normalized:
        normalized_link = normalize_url(item.link)
        if normalized_link not in seen_urls:
            seen_urls.add(normalized_link)
            unique_items_with_source.append((item, source, normalized_link))

    logger.info(
        "Dedup: %d total -> %d unique (removed %d duplicates)",
        len(all_normalized),
        len(unique_items_with_source),
        len(all_normalized) - len(unique_items_with_source),
    )

    # Skip articles already in DB to avoid redundant GPT calls.
    all_unique_urls = [normalized_url for _, _, normalized_url in unique_items_with_source]
    existing_urls = _query_existing_urls(all_unique_urls)
    new_items_with_source = [t for t in unique_items_with_source if t[2] not in existing_urls]
    new_items_with_source = _filter_recent_items(new_items_with_source)
    full_alias_index = build_player_alias_index()
    active_player_ids = get_active_player_ids()
    new_items_with_source = _filter_current_roster_items(
        new_items_with_source, full_alias_index, active_player_ids
    )
    logger.info(
        "DB/recent/roster filter: %d unique -> %d new (skipping %d existing, stale, or inactive-player-only)",
        len(unique_items_with_source),
        len(new_items_with_source),
        len(unique_items_with_source) - len(new_items_with_source),
    )

    enriched: list[dict] = []
    if new_items_with_source:
        new_items = [item for item, _, _ in new_items_with_source]
        enriched = _run_inference(new_items, full_alias_index)
        for enriched_item, (_, source, normalized_link) in zip(enriched, new_items_with_source, strict=True):
            enriched_item["collection_source"] = source
            enriched_item["normalized_url"] = normalized_link

    _, id_map = _upsert_articles(enriched)
    if len(id_map) < len(enriched):
        missing = len(enriched) - len(id_map)
        logger.warning("Upsert returned %d/%d IDs; falling back to re-query for %d missing", len(id_map), len(enriched), missing)
        id_map.update(_get_article_id_map(enriched))
    _save_labels_and_players(enriched, id_map)

    today = today_kst()
    try:
        game_collector.sync_game(today)
    except (RuntimeError, ValueError, RequestException) as exc:
        logger.warning("경기 데이터 동기화 실패 (무시): %s", exc)

    logger.info("News collection completed: %d items processed", len(new_items_with_source))
    return len(new_items_with_source)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    count = run()
    print(f"Processed articles: {count}")
    sys.exit(0)
