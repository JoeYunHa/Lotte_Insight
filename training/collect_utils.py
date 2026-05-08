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
    OPENAI_SUMMARY_BATCH_SIZE,
    OPENAI_SUMMARY_MAX_TOKENS,
    OPENAI_SUMMARY_MAX_WORKERS,
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
    "event_summary",
    "key_players",
    "lotte_stance",
    "game_ref",
    "game_context",
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

SUMMARY_SYSTEM_PROMPT = """You generate structured Korean article summaries for Lotte Giants news.

Return compact JSON only.

Rules:
- Use only the provided title, description snippet, article date, label, and game context.
- Do not invent facts that are not directly supported by the inputs.
- `event_summary` must be one Korean sentence, typically 30-80 characters.
- `key_players` must include 0-3 player names actually supported by the inputs.
- `lotte_stance` must be one of: positive, negative, neutral.
- `game_ref` is true only when the summary meaningfully uses the game context.

Return:
{
  "items": [
    {
      "index": 0,
      "event_summary": "롯데가 ...",
      "key_players": ["선수1"],
      "lotte_stance": "positive",
      "game_ref": true
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


# Removed a previously corrupted keyword block.


LOTTE_SIGNAL_KEYWORDS = ("롯데", "사직", "부산", "kbo", "프로야구")
MLB_GIANTS_EXPLICIT_KEYWORDS = (
    "샌프란시스코",
    "샌프 자이언츠",
    "sf 자이언츠",
    "san francisco giants",
    "oracle park",
)
MLB_GIANTS_CONTEXT_KEYWORDS = (
    "mlb",
    "메이저리그",
    "빅리그",
    "내셔널리그",
    "nl 서부",
)


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


_AGENCY_PREFIX_RE = re.compile(
    r"^\s*[\[\(【]"
    r"(?:연합뉴스|뉴시스|뉴스1|AFP|EPA|AP|로이터|Reuters|OSEN|스포츠조선|스포티비뉴스|MBC|SBS|KBS|YTN|채널A)"
    r"[\]\)】]\s*",
    re.IGNORECASE,
)
_REPORTER_SUFFIX_RE = re.compile(r"\s*[=|]?\s*[\w가-힣]{2,5}\s*(?:특파원|기자)\s*[=|]?\s*$")


def clean_snippet(text: str) -> str:
    """HTML 태그·통신사 prefix·기자명을 제거하고 정규화된 텍스트를 반환한다."""
    if not text:
        return text
    text = clean_html(text)
    text = _AGENCY_PREFIX_RE.sub("", text)
    text = _REPORTER_SUFFIX_RE.sub("", text)
    return text.strip()


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
            if is_mlb_giants_article(row):
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


def is_mlb_giants_article(row: dict, ensure_players: list[str] | None = None) -> bool:
    text = f"{row.get('title', '')} {row.get('description_snippet', '')}".strip()
    if not text:
        return False

    has_lotte_signal = _contains_any(text, LOTTE_SIGNAL_KEYWORDS)
    has_lotte_player = any(player in text for player in (ensure_players or []))
    if has_lotte_signal or has_lotte_player:
        return False

    if _contains_any(text, MLB_GIANTS_EXPLICIT_KEYWORDS):
        return True

    lowered = text.lower()
    has_giants = "자이언츠" in lowered or "giants" in lowered
    has_mlb_context = _contains_any(text, MLB_GIANTS_CONTEXT_KEYWORDS)
    return has_giants and has_mlb_context


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

    if is_mlb_giants_article(row, ensure_players=ensure_players):
        return _normalize_result(
            "ETC",
            [],
            False,
            confidence_score=RULE_CONFIDENCE_SCORE,
            detected_players=detected_players,
            confidence_note="excluded_mlb_giants",
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
        return _normalize_result(
            "INJURY_ROSTER",
            [],
            True,
            confidence_score=RULE_CONFIDENCE_SCORE,
            detected_players=detected_players,
        )

    if _contains_any(text, TRANSACTION_KEYWORDS):
        return _normalize_result(
            "TRANSACTION_CONTRACT",
            [],
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


def _build_summary_batch_payload(batch: list[tuple[int, dict]]) -> str:
    lines = ["Summarize each item and return JSON with an `items` array."]
    for output_index, row in batch:
        lines.append(f"\n[index={output_index}]")
        lines.append(f"title: {clean_snippet(str(row.get('title', '')))}")
        description = clean_snippet(str(row.get("description_snippet", "") or ""))
        if description:
            lines.append(f"description: {description[:ARTICLE_SNIPPET_LENGTH]}")
        published_at = row.get("published_at", "")
        if published_at:
            lines.append(f"published_at: {published_at}")
        primary_label = row.get("primary_label", "")
        if primary_label:
            lines.append(f"topic_label: {primary_label}")
        game_context = row.get("game_context", "")
        if game_context:
            lines.append(f"game_context: {game_context}")
    return "\n".join(lines)


def _parse_batch_response(response: dict, expected_indexes: set[int]) -> tuple[dict[int, dict], set[int]]:
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
        print(f"  [WARN] GPT partial response - missing {len(missing)} of {len(expected_indexes)} indexes: {sorted(missing)}")
    return parsed, missing


def call_label_gpt_batch(batch: list[tuple[int, dict, str]]) -> tuple[dict[int, dict], set[int]]:
    seq_to_actual = {seq: actual for seq, (actual, _, _) in enumerate(batch)}
    seq_batch = [(seq, row, extra) for seq, (_, row, extra) in enumerate(batch)]
    response = chat_json(
        LABELING_SYSTEM_PROMPT,
        _build_batch_payload(seq_batch),
        max_tokens=OPENAI_LABEL_MAX_TOKENS,
    )
    seq_parsed, seq_missing = _parse_batch_response(response, set(seq_to_actual.keys()))
    actual_parsed = {seq_to_actual[s]: v for s, v in seq_parsed.items()}
    actual_missing = {seq_to_actual[s] for s in seq_missing}
    return actual_parsed, actual_missing


def call_summary_gpt_batch(batch: list[tuple[int, dict]]) -> tuple[dict[int, dict], set[int]]:
    seq_to_actual = {seq: actual for seq, (actual, _) in enumerate(batch)}
    seq_batch = [(seq, row) for seq, (_, row) in enumerate(batch)]
    response = chat_json(
        SUMMARY_SYSTEM_PROMPT,
        _build_summary_batch_payload(seq_batch),
        max_tokens=OPENAI_SUMMARY_MAX_TOKENS,
    )
    seq_parsed, seq_missing = _parse_batch_response(response, set(seq_to_actual.keys()))
    actual_parsed = {seq_to_actual[s]: v for s, v in seq_parsed.items()}
    actual_missing = {seq_to_actual[s] for s in seq_missing}
    return actual_parsed, actual_missing


def safe_label(result: dict, row: dict, ensure_players: list[str] | None = None, *, source: str) -> dict:
    detected_players = _detect_players_local(row, ensure_players=ensure_players)
    confidence = RULE_CONFIDENCE_SCORE if source == "rule" else GPT_CONFIDENCE_SCORE
    normalized = _normalize_result(
        str(result.get("primary_label", "ETC")),
        result.get("secondary_labels") or [],
        bool(result.get("is_lotte_related", True)),
        confidence_score=confidence,
        detected_players=detected_players,
    )
    if is_mlb_giants_article(row, ensure_players=ensure_players):
        normalized["is_lotte_related"] = "false"
        normalized["confidence_note"] = (
            f"{normalized.get('confidence_note', '')};excluded_mlb_giants"
        ).strip(";")
    return normalized


def _normalize_summary_result(result: dict, row: dict) -> dict:
    key_players = result.get("key_players") or []
    if not isinstance(key_players, list):
        key_players = []

    normalized_players: list[str] = []
    for player in key_players:
        player_name = str(player or "").strip()
        if player_name and player_name not in normalized_players:
            normalized_players.append(player_name)
        if len(normalized_players) >= 3:
            break

    stance = str(result.get("lotte_stance", "neutral")).strip().lower()
    if stance not in {"positive", "negative", "neutral"}:
        stance = "neutral"

    game_ref = str(bool(result.get("game_ref", False))).lower()
    event_summary = str(result.get("event_summary", "") or "").strip()
    if not event_summary:
        fallback = f"{row.get('title', '')} {row.get('description_snippet', '')}".strip()
        event_summary = fallback[:80].strip()

    return {
        "event_summary": event_summary,
        "key_players": ";".join(normalized_players),
        "lotte_stance": stance,
        "game_ref": game_ref,
    }


def _iter_batches(items: list[tuple[int, dict, str]], batch_size: int) -> list[list[tuple[int, dict, str]]]:
    return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]


def _label_batch(batch: list[tuple[int, dict, str]], ensure_map: dict[int, list[str]]) -> list[tuple[int, dict]]:
    parsed, missing = call_label_gpt_batch(batch)
    labeled: list[tuple[int, dict]] = []
    for output_index, row, _extra_context in batch:
        if output_index in parsed:
            labeled.append(
                (
                    output_index,
                    safe_label(parsed[output_index], row, ensure_players=ensure_map.get(output_index), source="gpt"),
                )
            )
        else:
            # GPT가 이 인덱스를 누락 — 배치 전체 실패 대신 해당 행만 0점으로 표시
            labeled.append(
                (
                    output_index,
                    _normalize_result(
                        "ETC",
                        [],
                        True,
                        confidence_score=0.0,
                        detected_players=_detect_players_local(row, ensure_players=ensure_map.get(output_index)),
                        confidence_note="gpt_missing_index",
                    ),
                )
            )
    return labeled


def _summary_batch(batch: list[tuple[int, dict]]) -> list[tuple[int, dict]]:
    parsed, _missing = call_summary_gpt_batch(batch)
    summarized: list[tuple[int, dict]] = []
    for output_index, row in batch:
        if output_index in parsed:
            summarized.append((output_index, _normalize_summary_result(parsed[output_index], row)))
        else:
            summarized.append(
                (
                    output_index,
                    _normalize_summary_result(
                        {
                            "event_summary": "",
                            "key_players": [],
                            "lotte_stance": "neutral",
                            "game_ref": False,
                        },
                        row,
                    ),
                )
            )
    return summarized


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

    for output_index, row in enumerate(rows):
        ensure_players = ensure_map.get(output_index)
        if is_mlb_giants_article(row, ensure_players=ensure_players):
            rows[output_index]["is_lotte_related"] = "false"
            rows[output_index]["confidence_note"] = (
                f"{rows[output_index].get('confidence_note', '')};excluded_mlb_giants"
            ).strip(";")

    print(f"Auto labeling complete - success {ok} / fail {fail}")
    return rows


def build_game_context_for_row(row: dict) -> str:
    published_at = str(row.get("published_at", "") or "").strip()
    if not published_at:
        return "해당 날짜 경기 없음"

    try:
        parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(published_at[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return "해당 날짜 경기 없음"

    from collect_game_results import format_game_context, lookup_game

    game = lookup_game(parsed.date(), hour=parsed.hour)
    return format_game_context(game)


def add_structured_summaries(
    rows: list[dict],
    *,
    overwrite: bool = False,
    game_context_fn: Callable[[dict], str] | None = None,
) -> list[dict]:
    require_openai_api_key()

    candidates: list[tuple[int, dict]] = []
    for index, row in enumerate(rows):
        if game_context_fn:
            row["game_context"] = game_context_fn(row)
        else:
            row["game_context"] = row.get("game_context", "") or build_game_context_for_row(row)

        has_summary = bool(str(row.get("event_summary", "") or "").strip())
        if overwrite or not has_summary:
            candidates.append((index, row))

    if not candidates:
        print("Structured summaries already exist for all rows.")
        return rows

    print(
        f"\nStructured summary generation start - {len(candidates)} rows "
        f"(model: {OPENAI_MODEL}, workers: {OPENAI_SUMMARY_MAX_WORKERS})"
    )

    batches = _iter_batches(candidates, OPENAI_SUMMARY_BATCH_SIZE)
    completed = 0
    fail = 0
    with ThreadPoolExecutor(max_workers=OPENAI_SUMMARY_MAX_WORKERS) as executor:
        future_map = {executor.submit(_summary_batch, batch): batch for batch in batches}
        for future in as_completed(future_map):
            batch = future_map[future]
            completed += len(batch)
            try:
                summarized_batch = future.result()
                for output_index, summarized in summarized_batch:
                    rows[output_index].update(summarized)
            except Exception as exc:
                fail += len(batch)
                for output_index, row in batch:
                    rows[output_index].update(
                        _normalize_summary_result(
                            {
                                "event_summary": "",
                                "key_players": [],
                                "lotte_stance": "neutral",
                                "game_ref": False,
                            },
                            row,
                        )
                    )
                    rows[output_index]["confidence_note"] = (
                        f"{rows[output_index].get('confidence_note', '')};summary_failed:{exc}"
                    ).strip(";")
            print(f"  Summary progress {completed:>4}/{len(candidates)}  fail {fail}")
            time.sleep(AUTO_LABEL_SLEEP_SECONDS)

    print(f"Structured summary generation complete - rows {len(candidates)} / fail {fail}")
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


def load_csv_rows(out_csv) -> list[dict]:
    rows, _fieldnames = _load_existing_rows(out_csv)
    return rows


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


def rewrite_csv(rows: list[dict], out_csv) -> int:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_normalize_csv_row(row))
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
    "clean_snippet",
    "collect_news_by_keywords",
    "add_structured_summaries",
    "build_game_context_for_row",
    "fetch_naver",
    "fetch_naver_all",
    "item_to_row",
    "is_mlb_giants_article",
    "load_csv_rows",
    "load_existing_label_counts",
    "load_existing_titles",
    "parse_pub_date",
    "print_stats",
    "rewrite_csv",
    "write_csv",
]
