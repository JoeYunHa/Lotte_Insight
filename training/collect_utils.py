"""Shared utilities for training data collection and labeling."""

from __future__ import annotations

import csv
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests

from label_schema import VALID_LABEL_SET
from openai_utils import chat_json, require_openai_api_key
from settings import (
    ARTICLE_SNIPPET_LENGTH,
    AUTO_LABEL_SLEEP_SECONDS,
    COLLECT_REQUEST_SLEEP_SECONDS,
    DATA_DIR,
    NAVER_CLIENT_ID,
    NAVER_CLIENT_SECRET,
    NAVER_DISPLAY_LIMIT,
    NAVER_MAX_START,
    NAVER_SEARCH_URL,
    OPENAI_LABEL_BATCH_SIZE,
    OPENAI_LABEL_MAX_TOKENS,
    OPENAI_LABEL_MAX_WORKERS,
    OPENAI_MODEL,
)

CSV_HEADERS = [
    "id",
    "title",
    "description_snippet",
    "source_name",
    "published_at",
    "query_player",
    "primary_label",
    "secondary_labels",
    "confidence_score",
    "confidence_note",
    "detected_players",
    "is_lotte_related",
]

LEGACY_CSV_HEADERS = [
    "id",
    "title",
    "description_snippet",
    "source_name",
    "published_at",
    "primary_label",
    "secondary_labels",
    "confidence_score",
    "confidence_note",
    "detected_players",
    "is_lotte_related",
]

LABELING_SYSTEM_PROMPT = """You classify Korean baseball news about the Lotte Giants.

Return compact JSON only.

Valid labels:
- INJURY_ROSTER
- TRANSACTION_CONTRACT
- MATCH_RELATED
- PERFORMANCE_ANALYSIS
- INTERVIEW
- PLAYER_RELATED
- CLUB_OPERATION
- ETC

Rules:
- Use title and description snippet only.
- `is_lotte_related=true` only when Lotte, a Lotte player, or a Lotte game is a main topic.
- Secondary labels must exclude the primary label.
- Include a secondary label only when it is strongly supported.
- Use ETC only when none of the other labels fit.

Return:
{
  "items": [
    {
      "index": 0,
      "primary_label": "MATCH_RELATED",
      "secondary_labels": ["INTERVIEW"],
      "is_lotte_related": true
    }
  ]
}"""

RULE_CONFIDENCE_SCORE = 1.0
GPT_CONFIDENCE_SCORE = 0.9

BASEBALL_KEYWORDS = (
    "야구",
    "프로야구",
    "kbo",
    "투수",
    "타자",
    "포수",
    "감독",
    "코치",
    "선발",
    "불펜",
    "라인업",
    "등판",
    "말소",
    "등록",
    "복귀",
    "부상",
    "경기",
    "승리",
    "패배",
    "연패",
    "안타",
    "홈런",
    "타점",
    "세이브",
    "이닝",
    "타율",
    "ops",
    "era",
    "whip",
)

NON_BASEBALL_KEYWORDS = (
    "금리",
    "이자",
    "합병",
    "주가",
    "증권",
    "무공천",
    "의원",
    "정당",
    "출시",
    "브랜드",
    "넷플릭스",
)

INJURY_KEYWORDS = ("부상", "재활", "말소", "복귀", "엔트리", "등록", "결장", "수술")
TRANSACTION_KEYWORDS = ("영입", "방출", "트레이드", "계약", "fa", "입단", "이적", "재계약")


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_pub_date(raw: str) -> str:
    try:
        dt = datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return raw


def build_days_cutoff(days: int | None) -> str | None:
    if not days:
        return None
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")


def fetch_naver(keyword: str, display: int = NAVER_DISPLAY_LIMIT, start: int = 1) -> list[dict]:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("[ERROR] NAVER_CLIENT_ID / NAVER_CLIENT_SECRET environment variables are missing.")
        sys.exit(1)

    response = requests.get(
        NAVER_SEARCH_URL,
        headers={
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        },
        params={
            "query": keyword,
            "display": min(display, NAVER_DISPLAY_LIMIT),
            "start": max(1, min(start, NAVER_MAX_START)),
            "sort": "date",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("items", [])


def fetch_naver_all(keyword: str, max_items: int) -> list[dict]:
    """네이버 API 페이지네이션으로 최대 max_items건 수집."""
    all_items: list[dict] = []
    start = 1
    while len(all_items) < max_items and start <= NAVER_MAX_START:
        remaining = max_items - len(all_items)
        batch = fetch_naver(keyword, display=min(remaining, NAVER_DISPLAY_LIMIT), start=start)
        if not batch:
            break
        all_items.extend(batch)
        if len(batch) < NAVER_DISPLAY_LIMIT:
            break
        start += NAVER_DISPLAY_LIMIT
        time.sleep(COLLECT_REQUEST_SLEEP_SECONDS)
    return all_items


def item_to_row(item: dict) -> dict:
    url = item.get("originallink") or item.get("link", "")
    title = clean_html(item.get("title", ""))
    description = clean_html(item.get("description", ""))[:ARTICLE_SNIPPET_LENGTH]

    try:
        source = url.split("/")[2]
    except IndexError:
        source = ""

    return {
        "title": title,
        "description_snippet": description,
        "source_name": clean_html(source),
        "published_at": parse_pub_date(item.get("pubDate", "")),
        "query_player": "",
        "primary_label": "",
        "secondary_labels": "",
        "confidence_score": "",
        "confidence_note": "",
        "detected_players": "",
        "is_lotte_related": "",
        "_url": url,
    }


def load_existing_titles(out_csv) -> set[str]:
    """CSV에서 기존 제목 집합을 로드한다. 수집 시점 중복 제거에 사용."""
    if not out_csv.exists():
        return set()
    with out_csv.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return {row["title"] for row in reader if row.get("title")}


def load_existing_label_counts(out_csv) -> "Counter[str]":
    """CSV에서 라벨별 기존 건수를 반환한다."""
    if not out_csv.exists():
        return Counter()
    with out_csv.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return Counter(row["primary_label"] for row in reader if row.get("primary_label"))


def apply_label_cap(
    rows: list[dict],
    existing_counts: "Counter[str]",
    cap: int,
) -> tuple[list[dict], int]:
    """라벨별로 CSV 전체 누적이 cap을 넘지 않도록 new rows를 필터링한다.

    기존 건수가 이미 cap을 넘은 라벨은 새 행을 추가하지 않는다.
    라벨 미결정(빈 문자열) 행은 통과시킨다.
    """
    budget: Counter[str] = Counter()
    for label in existing_counts:
        budget[label] = max(0, cap - existing_counts[label])

    kept: list[dict] = []
    discarded = 0
    for row in rows:
        label = row.get("primary_label") or ""
        if not label:
            kept.append(row)
            continue
        if label not in budget:
            budget[label] = cap
        if budget[label] > 0:
            kept.append(row)
            budget[label] -= 1
        else:
            discarded += 1

    return kept, discarded


def collect_news_by_keywords(
    keywords: Iterable[str],
    *,
    days_cutoff: str | None,
    target_count: int | None = None,
    per_keyword_limit: int = NAVER_DISPLAY_LIMIT,
    per_keyword_dedupe: bool = False,
    existing_titles: set[str] | None = None,
    row_enricher: Callable[[str, dict], dict] | None = None,
    display: int = NAVER_DISPLAY_LIMIT,
) -> list[dict]:
    """키워드 목록으로 뉴스를 수집한다.

    per_keyword_limit > NAVER_DISPLAY_LIMIT(100)이면 자동으로 페이지네이션한다.
    existing_titles가 주어지면 수집 시점에 이미 알려진 제목을 건너뛴다.
    """
    rows: list[dict] = []
    seen_global: set[str] = set()
    skip_titles: set[str] = existing_titles or set()

    for keyword in keywords:
        if target_count is not None and len(rows) >= target_count:
            break

        print(f"  '{keyword}' ...", end=" ", flush=True)
        try:
            if per_keyword_limit > NAVER_DISPLAY_LIMIT:
                items = fetch_naver_all(keyword, max_items=per_keyword_limit)
            else:
                items = fetch_naver(keyword, display=display)
        except requests.RequestException as exc:
            print(f"failed ({exc})")
            continue

        added = 0
        seen_local: set[str] = set()

        for item in items:
            row = item_to_row(item)
            url = row.pop("_url")
            if not url:
                continue
            if days_cutoff and row["published_at"] < days_cutoff:
                continue
            if row["title"] in skip_titles:
                continue
            if per_keyword_dedupe:
                if url in seen_local:
                    continue
                seen_local.add(url)
            else:
                if url in seen_global:
                    continue
                seen_global.add(url)

            if row_enricher:
                row.update(row_enricher(keyword, row))

            rows.append(row)
            skip_titles.add(row["title"])
            added += 1

            if target_count is not None and len(rows) >= target_count:
                break

        print(f"{added} added (total {len(rows)})")
        if per_keyword_limit <= NAVER_DISPLAY_LIMIT:
            time.sleep(COLLECT_REQUEST_SLEEP_SECONDS)

    rows.sort(key=lambda row: row["published_at"], reverse=True)
    return rows if target_count is None else rows[:target_count]


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _detect_players_local(row: dict, ensure_players: list[str] | None = None) -> list[str]:
    text = f"{row.get('title', '')} {row.get('description_snippet', '')}"
    detected: list[str] = []
    for player in ensure_players or []:
        if player in text and player not in detected:
            detected.append(player)
    return detected


def _normalize_result(
    primary_label: str,
    secondary_labels: list[str] | None,
    is_lotte_related: bool,
    *,
    confidence_score: float,
    detected_players: list[str] | None,
    confidence_note: str = "",
) -> dict:
    primary = primary_label if primary_label in VALID_LABEL_SET else "ETC"

    secondary: list[str] = []
    for label in secondary_labels or []:
        if label in VALID_LABEL_SET and label != primary and label not in secondary:
            secondary.append(label)

    return {
        "primary_label": primary,
        "secondary_labels": ";".join(secondary),
        "confidence_score": round(confidence_score, 2),
        "confidence_note": confidence_note.strip(),
        "detected_players": ";".join(detected_players or []),
        "is_lotte_related": str(bool(is_lotte_related)).lower(),
    }


def _rule_label_row(row: dict, ensure_players: list[str] | None = None) -> dict | None:
    text = f"{row.get('title', '')} {row.get('description_snippet', '')}".strip()
    detected_players = _detect_players_local(row, ensure_players=ensure_players)

    if not text:
        return _normalize_result(
            "ETC",
            [],
            False,
            confidence_score=RULE_CONFIDENCE_SCORE,
            detected_players=detected_players,
        )

    has_baseball = _contains_any(text, BASEBALL_KEYWORDS)
    has_non_baseball = _contains_any(text, NON_BASEBALL_KEYWORDS)

    if has_non_baseball and not has_baseball:
        return _normalize_result(
            "ETC",
            [],
            False,
            confidence_score=RULE_CONFIDENCE_SCORE,
            detected_players=detected_players,
        )

    if not has_baseball:
        return None

    if _contains_any(text, INJURY_KEYWORDS):
        secondary = ["PLAYER_RELATED"] if detected_players else []
        return _normalize_result(
            "INJURY_ROSTER",
            secondary,
            True,
            confidence_score=RULE_CONFIDENCE_SCORE,
            detected_players=detected_players,
        )

    if _contains_any(text, TRANSACTION_KEYWORDS):
        secondary = ["PLAYER_RELATED"] if detected_players else []
        return _normalize_result(
            "TRANSACTION_CONTRACT",
            secondary,
            True,
            confidence_score=RULE_CONFIDENCE_SCORE,
            detected_players=detected_players,
        )

    return None


def _build_batch_payload(batch: list[tuple[int, dict, str]]) -> str:
    lines = ["Classify each item and return JSON with an `items` array."]
    for output_index, row, extra_context in batch:
        lines.append(f"\n[index={output_index}]")
        lines.append(f"title: {row.get('title', '')}")
        description = row.get("description_snippet", "")
        if description:
            lines.append(f"description: {description}")
        if extra_context:
            lines.append(f"context: {extra_context}")
    return "\n".join(lines)


def _parse_batch_response(response: dict, expected_indexes: set[int]) -> dict[int, dict]:
    items = response.get("items")
    if not isinstance(items, list):
        raise ValueError("Missing items array in GPT response")

    parsed: dict[int, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if isinstance(index, int) and index in expected_indexes:
            parsed[index] = item

    missing = expected_indexes - set(parsed)
    if missing:
        raise ValueError(f"Incomplete GPT batch response. Missing indexes: {sorted(missing)}")
    return parsed


def call_label_gpt_batch(batch: list[tuple[int, dict, str]]) -> dict[int, dict]:
    response = chat_json(
        LABELING_SYSTEM_PROMPT,
        _build_batch_payload(batch),
        max_tokens=OPENAI_LABEL_MAX_TOKENS,
    )
    return _parse_batch_response(response, {output_index for output_index, _row, _extra in batch})


def safe_label(result: dict, row: dict, ensure_players: list[str] | None = None, *, source: str) -> dict:
    detected_players = _detect_players_local(row, ensure_players=ensure_players)
    confidence = RULE_CONFIDENCE_SCORE if source == "rule" else GPT_CONFIDENCE_SCORE
    return _normalize_result(
        str(result.get("primary_label", "ETC")),
        result.get("secondary_labels") or [],
        bool(result.get("is_lotte_related", True)),
        confidence_score=confidence,
        detected_players=detected_players,
    )


def _iter_batches(items: list[tuple[int, dict, str]], batch_size: int) -> list[list[tuple[int, dict, str]]]:
    return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]


def _label_batch(batch: list[tuple[int, dict, str]], ensure_map: dict[int, list[str]]) -> list[tuple[int, dict]]:
    parsed = call_label_gpt_batch(batch)
    labeled: list[tuple[int, dict]] = []
    for output_index, row, _extra_context in batch:
        labeled.append(
            (
                output_index,
                safe_label(parsed[output_index], row, ensure_players=ensure_map.get(output_index), source="gpt"),
            )
        )
    return labeled


def auto_label(
    rows: list[dict],
    extra_context_fn: Callable[[dict], str] | None = None,
    ensure_players_fn: Callable[[dict], list[str]] | None = None,
) -> list[dict]:
    require_openai_api_key()

    total = len(rows)
    print(f"\nAuto labeling start - {total} rows (model: {OPENAI_MODEL})")

    ok = 0
    fail = 0
    rule_hits = 0
    gpt_candidates: list[tuple[int, dict, str]] = []
    ensure_map: dict[int, list[str]] = {}

    for output_index, row in enumerate(rows):
        extra_context = extra_context_fn(row) if extra_context_fn else ""
        ensure_players = ensure_players_fn(row) if ensure_players_fn else None
        ensure_map[output_index] = ensure_players or []

        rule_result = _rule_label_row(row, ensure_players=ensure_players)
        if rule_result is not None:
            row.update(rule_result)
            ok += 1
            rule_hits += 1
        else:
            gpt_candidates.append((output_index, row, extra_context))

        processed = output_index + 1
        if processed % 10 == 0 or processed == total:
            pct = processed / total * 100 if total else 100
            print(f"  [{processed:>4}/{total}] {pct:5.1f}%  rule {rule_hits}  queued {len(gpt_candidates)}")

    batches = _iter_batches(gpt_candidates, OPENAI_LABEL_BATCH_SIZE)
    if batches:
        print(
            f"\nGPT batched labeling - rows {len(gpt_candidates)}, "
            f"batches {len(batches)}, workers {OPENAI_LABEL_MAX_WORKERS}"
        )
        with ThreadPoolExecutor(max_workers=OPENAI_LABEL_MAX_WORKERS) as executor:
            future_map = {executor.submit(_label_batch, batch, ensure_map): batch for batch in batches}
            completed = 0
            for future in as_completed(future_map):
                batch = future_map[future]
                completed += len(batch)
                try:
                    labeled_batch = future.result()
                    for output_index, labeled in labeled_batch:
                        rows[output_index].update(labeled)
                        ok += 1
                except Exception as exc:
                    for output_index, row, _extra_context in batch:
                        rows[output_index].update(
                            _normalize_result(
                                "ETC",
                                [],
                                True,
                                confidence_score=0.0,
                                detected_players=_detect_players_local(
                                    row,
                                    ensure_players=ensure_map.get(output_index),
                                ),
                                confidence_note=f"GPT call failed: {exc}",
                            )
                        )
                        fail += 1
                print(f"  GPT progress {completed:>4}/{len(gpt_candidates)}  success {ok}  fail {fail}")
                time.sleep(AUTO_LABEL_SLEEP_SECONDS)

    print(f"Auto labeling complete - success {ok} / fail {fail}")
    return rows


def _normalize_csv_row(row: dict | None) -> dict:
    normalized = {header: "" for header in CSV_HEADERS}
    if not row:
        return normalized

    extra_values = row.get(None) or []
    if not isinstance(extra_values, list):
        extra_values = [extra_values]

    has_legacy_shape = (
        "query_player" not in row
        and any(key in row for key in LEGACY_CSV_HEADERS)
    )

    if has_legacy_shape and extra_values:
        normalized["id"] = str(row.get("id", "") or "")
        normalized["title"] = str(row.get("title", "") or "")
        normalized["description_snippet"] = str(row.get("description_snippet", "") or "")
        normalized["source_name"] = str(row.get("source_name", "") or "")
        normalized["published_at"] = str(row.get("published_at", "") or "")
        normalized["query_player"] = str(row.get("primary_label", "") or "")
        normalized["primary_label"] = str(row.get("secondary_labels", "") or "")
        normalized["secondary_labels"] = str(row.get("confidence_score", "") or "")
        normalized["confidence_score"] = str(row.get("confidence_note", "") or "")
        normalized["confidence_note"] = str(row.get("detected_players", "") or "")
        normalized["detected_players"] = str(row.get("is_lotte_related", "") or "")
        normalized["is_lotte_related"] = str(extra_values[0] or "")
        return normalized

    for header in CSV_HEADERS:
        normalized[header] = str(row.get(header, "") or "")
    return normalized


def _load_existing_rows(out_csv) -> tuple[list[dict], list[str]]:
    if not out_csv.exists():
        return [], []

    with out_csv.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        rows = [_normalize_csv_row(row) for row in reader]
    return rows, fieldnames


def write_csv(rows: list[dict], out_csv, append: bool) -> int:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    start_id = 1
    existing_titles: set[str] = set()
    existing_rows: list[dict] = []
    rewrite_existing = False

    if append and out_csv.exists():
        existing_rows, existing_headers = _load_existing_rows(out_csv)
        rewrite_existing = existing_headers != CSV_HEADERS
        if existing_rows:
            start_id = max(int(row["id"]) for row in existing_rows if str(row.get("id", "")).isdigit()) + 1
        existing_titles = {row["title"] for row in existing_rows}
        rows = [row for row in rows if row["title"] not in existing_titles]
        if rewrite_existing:
            mode, write_header = "w", True
        else:
            mode, write_header = "a", False
    else:
        mode, write_header = "w", True

    if not rows and not rewrite_existing:
        print("No new articles to save.")
        return 0

    with out_csv.open(mode, encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_HEADERS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        if rewrite_existing:
            for row in existing_rows:
                writer.writerow(_normalize_csv_row(row))
        for offset, row in enumerate(rows):
            normalized = _normalize_csv_row(row)
            normalized["id"] = str(start_id + offset)
            writer.writerow(normalized)

    return len(rows)


def print_stats(rows: list[dict]) -> None:
    counts: Counter[str] = Counter()
    low_confidence_count = 0

    for row in rows:
        label = row.get("primary_label")
        if label:
            counts[label] += 1
        score = row.get("confidence_score")
        if score and float(score) < 0.7:
            low_confidence_count += 1

    print("\nLabel distribution")
    for label in sorted(VALID_LABEL_SET):
        print(f"  {label:<25} {counts.get(label, 0):>4}")
    print(f"\nconfidence < 0.7 review count: {low_confidence_count}")


__all__ = [
    "BASEBALL_KEYWORDS",
    "CSV_HEADERS",
    "DATA_DIR",
    "NON_BASEBALL_KEYWORDS",
    "apply_label_cap",
    "auto_label",
    "build_days_cutoff",
    "clean_html",
    "collect_news_by_keywords",
    "fetch_naver",
    "fetch_naver_all",
    "item_to_row",
    "load_existing_label_counts",
    "load_existing_titles",
    "parse_pub_date",
    "print_stats",
    "write_csv",
]
