"""
뉴스 수집·라벨링 파이프라인 공통 유틸리티.
collect_for_labeling.py (팀)과 collect_players.py (선수)에서 공유.
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL        = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"
DATA_DIR = Path(__file__).parent / "data"

CSV_HEADERS = [
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

VALID_LABELS = {
    "INJURY_ROSTER",
    "TRANSACTION_CONTRACT",
    "MATCH_RELATED",
    "PERFORMANCE_ANALYSIS",
    "INTERVIEW",
    "PLAYER_RELATED",
    "CLUB_OPERATION",
    "ETC",
}

LABELING_SYSTEM_PROMPT = """당신은 KBO 롯데 자이언츠 뉴스 기사를 분류하는 전문가입니다.
기사 제목과 description snippet만 보고 아래 규칙에 따라 JSON을 반환하세요.

## 라벨 정의 및 우선순위 (위일수록 우선)
1. INJURY_ROSTER        — 부상·재활·복귀·엔트리 등록/말소·콜업·2군행
2. TRANSACTION_CONTRACT — 영입·방출·트레이드·계약·연봉·이적
3. MATCH_RELATED        — 경기 결과·선발·불펜·타선·라인업·연승/연패·리뷰
4. PERFORMANCE_ANALYSIS — 타율·ERA·OPS·기록·순위·성적 지표 분석
5. INTERVIEW            — 감독·선수·관계자 발언·인터뷰 중심
6. PLAYER_RELATED       — 특정 선수 중심 (부상·계약·지표 분석 제외)
7. CLUB_OPERATION       — 구단 운영·구장·팬 행사·마케팅
8. ETC                  — 위 범주 해당 없음 또는 판단 불가

## 경계 케이스 규칙
- 선수명 포함 + 부상·말소 → INJURY_ROSTER
- 선수명 포함 + 영입·방출·계약 → TRANSACTION_CONTRACT
- 선수명 포함 + 성적/지표 분석 → PERFORMANCE_ANALYSIS
- 경기 후 발언이 제목 중심 → INTERVIEW (경기 결과가 중심이면 MATCH_RELATED)
- 여러 라벨 가능 시 → 우선순위 높은 것이 primary_label

## is_lotte_related 판단
- true: 롯데 소속 선수·구단·경기가 기사의 주체
- false: 롯데가 상대팀으로만 언급되거나 KBO 전체 기사에서 부수적 언급

## 출력 형식 (JSON만 반환, 설명 없음)
{
  "primary_label": "<라벨>",
  "secondary_labels": ["<라벨>", ...],
  "confidence_score": <0.0~1.0>,
  "confidence_note": "<판단 어려운 경우만 한 줄, 아니면 빈 문자열>",
  "detected_players": ["<선수명>", ...],
  "is_lotte_related": <true|false>
}"""


# ── Naver 수집 ────────────────────────────────────────────────────────────────

def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_pub_date(raw: str) -> str:
    try:
        dt = datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return raw


def fetch_naver(keyword: str, display: int = 100) -> list[dict]:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("[ERROR] NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 없습니다.")
        sys.exit(1)
    resp = requests.get(
        NAVER_SEARCH_URL,
        headers={
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        },
        params={"query": keyword, "display": min(display, 100), "sort": "date"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def item_to_row(item: dict) -> dict:
    url = item.get("originallink") or item.get("link", "")
    title = clean_html(item.get("title", ""))
    desc  = clean_html(item.get("description", ""))[:120]
    try:
        source = url.split("/")[2]
    except IndexError:
        source = ""
    return {
        "title":               title,
        "description_snippet": desc,
        "source_name":         clean_html(source),
        "published_at":        parse_pub_date(item.get("pubDate", "")),
        "primary_label":       "",
        "secondary_labels":    "",
        "confidence_score":    "",
        "confidence_note":     "",
        "detected_players":    "",
        "is_lotte_related":    "",
        "_url":                url,
    }


# ── GPT 라벨링 ───────────────────────────────────────────────────────────────

def call_gpt(title: str, description: str, extra_context: str = "") -> dict:
    user_content = f"제목: {title}"
    if description:
        user_content += f"\ndescription: {description}"
    if extra_context:
        user_content += f"\n{extra_context}"

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model":           OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": LABELING_SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            "max_tokens":      200,
            "temperature":     0.0,
            "response_format": {"type": "json_object"},
        },
        timeout=20,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


def safe_label(result: dict, ensure_players: list[str] | None = None) -> dict:
    """
    GPT 응답 정규화.
    ensure_players: 반드시 detected_players에 포함시킬 선수명 목록
                    (선수별 파이프라인에서 검색 키워드 선수 보장 용도)
    """
    primary = result.get("primary_label", "ETC")
    if primary not in VALID_LABELS:
        primary = "ETC"

    secondary = [
        lbl for lbl in (result.get("secondary_labels") or [])
        if lbl in VALID_LABELS and lbl != primary
    ]

    try:
        confidence = float(result.get("confidence_score", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.5

    gpt_players = [str(p) for p in (result.get("detected_players") or [])]
    if ensure_players:
        for p in ensure_players:
            if p not in gpt_players:
                gpt_players.insert(0, p)

    is_lotte = result.get("is_lotte_related", True)

    return {
        "primary_label":    primary,
        "secondary_labels": ";".join(secondary),
        "confidence_score": round(confidence, 2),
        "confidence_note":  (result.get("confidence_note") or "").strip(),
        "detected_players": ";".join(gpt_players),
        "is_lotte_related": str(is_lotte).lower(),
    }


def auto_label(
    rows: list[dict],
    extra_context_fn=None,
    ensure_players_fn=None,
) -> list[dict]:
    """
    rows를 순차 GPT 호출로 라벨링한다.

    extra_context_fn(row) -> str | None  : 행별 추가 컨텍스트 문자열 반환 함수
    ensure_players_fn(row) -> list[str]  : 반드시 포함할 선수명 목록 반환 함수
    """
    if not OPENAI_API_KEY:
        print("[ERROR] OPENAI_API_KEY 환경변수가 없습니다.")
        sys.exit(1)

    total = len(rows)
    print(f"\n자동 라벨링 시작 — {total}건 (모델: {OPENAI_MODEL})")
    ok = fail = 0

    for i, row in enumerate(rows):
        extra = extra_context_fn(row) if extra_context_fn else ""
        ensure = ensure_players_fn(row) if ensure_players_fn else None
        try:
            result = call_gpt(row["title"], row["description_snippet"], extra)
            row.update(safe_label(result, ensure_players=ensure))
            ok += 1
        except Exception as e:
            row.update({
                "primary_label":    "ETC",
                "secondary_labels": "",
                "confidence_score": "0.0",
                "confidence_note":  f"GPT 호출 실패: {e}",
                "detected_players": ";".join(ensure or []),
                "is_lotte_related": "true",
            })
            fail += 1

        if (i + 1) % 10 == 0 or (i + 1) == total:
            pct = (i + 1) / total * 100
            print(f"  [{i+1:>4}/{total}] {pct:5.1f}%  성공 {ok}  실패 {fail}", flush=True)

        time.sleep(0.15)

    print(f"라벨링 완료 — 성공 {ok}건 / 실패 {fail}건")
    return rows


# ── CSV I/O ───────────────────────────────────────────────────────────────────

def write_csv(rows: list[dict], out_csv: Path, append: bool) -> int:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    start_id = 1
    existing_titles: set[str] = set()

    if append and out_csv.exists():
        with out_csv.open("r", encoding="utf-8-sig", newline="") as f:
            existing = list(csv.DictReader(f))
        if existing:
            start_id = max(int(r["id"]) for r in existing) + 1
        existing_titles = {r["title"] for r in existing}
        rows = [r for r in rows if r["title"] not in existing_titles]
        mode, write_header = "a", False
    else:
        mode, write_header = "w", True

    if not rows:
        print("추가할 새 기사가 없습니다 (모두 중복).")
        return 0

    with out_csv.open(mode, encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for i, row in enumerate(rows):
            row["id"] = start_id + i
            writer.writerow(row)

    return len(rows)


def print_stats(rows: list[dict]) -> None:
    from collections import Counter
    counts = Counter(r["primary_label"] for r in rows if r["primary_label"])
    low_conf = [r for r in rows if r.get("confidence_score") and float(r["confidence_score"]) < 0.7]

    print("\n── 라벨 분포 ──────────────────────────")
    for label in [
        "MATCH_RELATED", "PLAYER_RELATED", "INJURY_ROSTER",
        "INTERVIEW", "PERFORMANCE_ANALYSIS", "TRANSACTION_CONTRACT",
        "CLUB_OPERATION", "ETC",
    ]:
        bar = "█" * counts.get(label, 0)
        print(f"  {label:<25} {counts.get(label, 0):>4}건  {bar}")
    print(f"\n  confidence < 0.7 (검수 권장): {len(low_conf)}건")
    print("────────────────────────────────────────")
