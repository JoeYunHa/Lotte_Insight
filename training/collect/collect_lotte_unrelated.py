"""
Collect is_lotte_related=False samples for binary classifier training.

현재 labeled_titles.csv 의 불균형 현황:
  True  4,691건 (97.6%)
  False   114건  (2.4%)

전략:
  1. 비-롯데 KBO 9개 팀 키워드 → 야구 맥락의 False 샘플 (hard negative)
  2. 상업적 롯데 계열사 키워드 → 롯데 이름이 들어가지만 야구와 무관한 False 샘플

필터링:
  - 강한 롯데 자이언츠 지시어("롯데 자이언츠", "자이언츠", "사직구장" 등)가 포함된
    기사는 제외 — 실제 True 기사가 섞일 수 있음
  - "롯데"가 상대팀으로 잠깐 언급된 기사는 유지 (분류기가 구분해야 하는 hard negative)

라벨링:
  - is_lotte_related: 항상 "false" (결정론적 강제)
  - primary_label: --label 플래그 시 GPT 사용, 기본은 ETC (비용 절감)

출력: training/data/labeled_titles.csv 에 append
목표: False 샘플 400건 추가 → 비율 약 10% False
"""

from __future__ import annotations

import argparse

from training.collect.collect_utils import (
    auto_label,
    build_days_cutoff,
    collect_news_by_keywords,
    load_existing_titles,
    write_csv,
)
from settings import LABELED_TITLES_CSV, NAVER_DISPLAY_LIMIT, NAVER_MAX_START

# 강한 롯데 자이언츠 지시어 — 포함 시 해당 기사 제외
_LOTTE_GIANTS_STRONG: frozenset[str] = frozenset({
    "롯데 자이언츠",
    "자이언츠",
    "사직구장",
    "사직야구장",
    "롯데전",
    "자이언츠전",
    "부산 야구",
    "롯데 야구",
    "롯데 선발",
    "롯데 불펜",
    "롯데 타선",
    "롯데 감독",
    "롯데 구단",
    "롯데 선수",
    "롯데 홈런",
    "롯데 승리",
    "롯데 패배",
    "롯데 FA",
    "롯데 트레이드",
})

# 비-롯데 KBO 팀 키워드
NON_LOTTE_TEAM_KEYWORDS: list[str] = [
    "삼성 라이온즈",
    "KIA 타이거즈",
    "LG 트윈스",
    "두산 베어스",
    "SSG 랜더스",
    "NC 다이노스",
    "키움 히어로즈",
    "한화 이글스",
    "KT 위즈",
    # 팀별 경기/이슈 키워드 추가
    "삼성 선발",
    "KIA 타자",
    "LG 불펜",
    "두산 감독",
    "SSG 외국인",
    "NC 부상",
    "키움 트레이드",
    "한화 콜업",
    "KT 타선",
]

# 상업적 롯데 계열사 키워드 (야구와 무관한 롯데 언급)
COMMERCIAL_LOTTE_KEYWORDS: list[str] = [
    "롯데백화점",
    "롯데월드",
    "롯데마트",
    "롯데그룹",
    "롯데칠성",
    "롯데케미칼",
    "롯데면세점",
    "롯데카드",
    "롯데건설",
]

DEFAULT_TARGET = 400
PHOTO_PREFIXES = ("[포토", "[사진")


def _has_lotte_giants_indicator(text: str) -> bool:
    return any(kw in text for kw in _LOTTE_GIANTS_STRONG)


def _filter_rows(rows: list[dict]) -> tuple[list[dict], int]:
    """강한 롯데 자이언츠 지시어가 포함된 기사 제거."""
    kept: list[dict] = []
    removed = 0
    for row in rows:
        text = f"{row.get('title', '')} {row.get('description_snippet', '')}"
        if _has_lotte_giants_indicator(text):
            removed += 1
            continue
        if row.get("title", "").startswith(PHOTO_PREFIXES):
            removed += 1
            continue
        kept.append(row)
    return kept, removed


def _force_false_label(rows: list[dict]) -> list[dict]:
    """is_lotte_related를 false로 강제. primary_label이 비어 있으면 ETC로 채운다."""
    for row in rows:
        row["is_lotte_related"] = "false"
        if not row.get("primary_label"):
            row["primary_label"] = "ETC"
            row["confidence_score"] = "1.0"
            row["confidence_note"] = "forced_false_sample"
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect is_lotte_related=False samples for binary classifier training."
    )
    parser.add_argument(
        "--target", type=int, default=DEFAULT_TARGET,
        help=f"Target number of new False rows to add (default: {DEFAULT_TARGET})"
    )
    parser.add_argument(
        "--days", type=int, default=None,
        help="Only collect articles from the last N days"
    )
    parser.add_argument(
        "--per-keyword", type=int, default=NAVER_DISPLAY_LIMIT,
        help=f"Max items per keyword (1-{NAVER_MAX_START})"
    )
    parser.add_argument(
        "--label", action="store_true",
        help="Use GPT to assign primary_label (costs ~$0.01/100건). Default: ETC."
    )
    parser.add_argument(
        "--commercial-only", action="store_true",
        help="Collect only commercial Lotte keywords (skip KBO team keywords)"
    )
    parser.add_argument(
        "--kbo-only", action="store_true",
        help="Collect only non-Lotte KBO team keywords"
    )
    args = parser.parse_args()

    per_keyword = max(1, min(args.per_keyword, NAVER_MAX_START))
    cutoff = build_days_cutoff(args.days)

    if args.commercial_only:
        keywords = COMMERCIAL_LOTTE_KEYWORDS
    elif args.kbo_only:
        keywords = NON_LOTTE_TEAM_KEYWORDS
    else:
        keywords = NON_LOTTE_TEAM_KEYWORDS + COMMERCIAL_LOTTE_KEYWORDS

    existing_titles = load_existing_titles(LABELED_TITLES_CSV)
    print(f"기존 CSV 제목 수: {len(existing_titles)}")
    print(f"키워드 수: {len(keywords)}  per-keyword: {per_keyword}  target: {args.target}")

    print("\n[1/3] 뉴스 수집")
    rows = collect_news_by_keywords(
        keywords,
        days_cutoff=cutoff,
        target_count=args.target * 3,  # 필터링 후 여유분 확보
        per_keyword_limit=per_keyword,
        existing_titles=existing_titles,
    )
    print(f"수집 완료: {len(rows)}건")

    rows, removed = _filter_rows(rows)
    print(f"롯데 자이언츠 지시어 포함 제거: {removed}건  남은 행: {len(rows)}건")

    rows = rows[: args.target]
    print(f"target {args.target}건으로 자름: {len(rows)}건")

    if not rows:
        print("수집된 기사 없음 — 종료")
        return

    if args.label:
        print("\n[2/3] GPT primary_label 라벨링")
        rows = auto_label(rows)
        # GPT가 is_lotte_related=true로 잘못 판정할 수 있으므로 강제 덮어쓰기
        rows = _force_false_label(rows)
    else:
        print("\n[2/3] 라벨링 생략 (--label 미지정) — primary_label=ETC 설정")
        rows = _force_false_label(rows)

    false_count = sum(1 for r in rows if str(r.get("is_lotte_related", "")).lower() == "false")
    print(f"\n[3/3] CSV 저장 → {LABELED_TITLES_CSV}")
    print(f"  is_lotte_related=false: {false_count}건")
    saved = write_csv(rows, LABELED_TITLES_CSV, append=True)
    print(f"  저장 완료: {saved}건")


if __name__ == "__main__":
    main()
