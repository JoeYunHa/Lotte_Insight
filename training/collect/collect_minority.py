"""Collect minority-class articles with per-label day windows and focus-only keywords."""

from __future__ import annotations

import argparse
from collections import Counter

from training.collect.collect_for_labeling import build_keywords, filter_photo_captions
from training.collect.collect_utils import (
    BASEBALL_KEYWORDS,
    NON_BASEBALL_KEYWORDS,
    apply_label_cap,
    auto_label,
    build_days_cutoff,
    collect_news_by_keywords,
    is_mlb_giants_article,
    load_existing_label_counts,
    load_existing_titles,
    print_stats,
    write_csv,
)
from settings import LABELED_TITLES_CSV, NAVER_DISPLAY_LIMIT, TEAM_ALIASES

# 라벨별 수집 설정
# direct=True: GPT 라벨 필터 없이 수집 키워드 기반으로 라벨 직접 부여
#   - INTERVIEW·CLUB_OPERATION은 경기 내용과 겹쳐 GPT가 항상 고우선순위 라벨을 선택하므로
#     키워드 특이도(specificity)에 의존한 직접 부여 방식을 사용한다.
# direct=False: GPT 라벨링 후 primary/secondary 필터 적용 (기존 방식)
MINORITY_CONFIG: dict[str, dict] = {
    "INTERVIEW":            {"days": 365, "count": 200, "cap": 200, "direct": True},
    "CLUB_OPERATION":       {"days": 365, "count": 150, "cap": 150, "direct": True},
    "TRANSACTION_CONTRACT": {"days": 365, "count": 200, "cap": 200, "direct": False},
    "PERFORMANCE_ANALYSIS": {"days": 180, "count": 200, "cap": 250, "direct": False},
}


def _has_any(text: str, keywords: tuple) -> bool:
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in keywords)


def _direct_assign(rows: list[dict], target_label: str) -> list[dict]:
    """GPT 라벨링 없이 기본 필터만 적용하고 target_label을 직접 부여한다.

    통과 조건:
    - 비야구 키워드 단독 존재 시 제외
    - MLB 자이언츠 기사 제외
    - 롯데 관련 키워드 없으면 제외
    """
    result: list[dict] = []
    for row in rows:
        text = f"{row.get('title', '')} {row.get('description_snippet', '')}"
        if _has_any(text, NON_BASEBALL_KEYWORDS) and not _has_any(text, BASEBALL_KEYWORDS):
            continue
        if is_mlb_giants_article(row):
            continue
        if not any(alias in text for alias in TEAM_ALIASES):
            continue
        row = dict(row)
        row["primary_label"] = target_label
        row["secondary_labels"] = ""
        row["confidence_score"] = "1.0"
        row["confidence_note"] = "direct_keyword"
        row["is_lotte_related"] = "true"
        result.append(row)
    return result


def _filter_and_promote(rows: list[dict], target_label: str) -> list[dict]:
    """primary 또는 secondary에 target_label이 있는 행만 유지.

    secondary에만 있는 경우 primary를 target_label로 승격한다.
    GPT가 이미 해당 라벨을 인정했으므로 학습 데이터 품질이 유지된다.
    """
    result: list[dict] = []
    promoted = 0
    for row in rows:
        primary = row.get("primary_label", "")
        secondary_raw = row.get("secondary_labels", "") or ""
        secondaries = [s.strip() for s in secondary_raw.split(";") if s.strip()]

        if primary == target_label:
            result.append(row)
        elif target_label in secondaries:
            row = dict(row)
            row["primary_label"] = target_label
            result.append(row)
            promoted += 1

    if promoted:
        print(f"  secondary→primary 승격: {promoted}건")
    return result


def _run_label(
    label: str,
    cfg: dict,
    per_keyword: int,
    existing_titles: set[str],
    existing_counts: Counter,
    dry_run: bool,
) -> list[dict]:
    cap = cfg["cap"]
    current = existing_counts.get(label, 0)
    if current >= cap:
        print(f"  [{label}] 현재 {current}건 ≥ cap {cap} — 건너뜀")
        return []

    keywords = build_keywords([label], focus_only=True)
    if not keywords:
        print(f"  [{label}] FOCUS_LABEL_KEYWORDS 없음 — 건너뜀")
        return []

    days, count = cfg["days"], cfg["count"]
    cutoff = build_days_cutoff(days)
    budget = cap - current
    effective_count = min(count, budget)

    print(f"\n[{label}] days={days}  target={effective_count}  cap={cap}  현재={current}  키워드={len(keywords)}개")

    rows = collect_news_by_keywords(
        keywords,
        days_cutoff=cutoff,
        target_count=effective_count,
        per_keyword_limit=per_keyword,
        existing_titles=existing_titles,
    )
    rows = filter_photo_captions(rows)
    print(f"  수집: {len(rows)}건")

    if not rows or dry_run:
        return rows

    if cfg.get("direct"):
        rows = _direct_assign(rows, label)
        print(f"  직접 부여 후: {len(rows)}건")
    else:
        rows = auto_label(rows)
        rows = _filter_and_promote(rows, label)
        print(f"  라벨 필터 후: {len(rows)}건")

    rows, discarded = apply_label_cap(rows, existing_counts, cap)
    if discarded:
        print(f"  cap 적용: {discarded}건 폐기, {len(rows)}건 유지")

    for row in rows:
        existing_titles.add(row["title"])

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect minority-class articles with per-label day windows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            f"  {label:<25} days={cfg['days']:<5} cap={cfg['cap']}"
            for label, cfg in MINORITY_CONFIG.items()
        ),
    )
    parser.add_argument(
        "--labels",
        type=str,
        default=",".join(MINORITY_CONFIG),
        help="수집할 라벨 (콤마 구분, 기본값: 전체 소수 라벨)",
    )
    parser.add_argument(
        "--per-keyword",
        type=int,
        default=300,
        help="키워드당 최대 수집 건수 (기본=300, 100 초과 시 페이지네이션 자동 적용)",
    )
    parser.add_argument("--dry-run", action="store_true", help="수집만 수행, 라벨링·저장 건너뜀")
    parser.add_argument("--overwrite", action="store_true", help="기존 CSV 덮어쓰기")
    args = parser.parse_args()

    target_labels = [lb.strip() for lb in args.labels.split(",") if lb.strip()]
    invalid = [lb for lb in target_labels if lb not in MINORITY_CONFIG]
    if invalid:
        raise SystemExit(f"지원하지 않는 라벨: {', '.join(invalid)}\n지원 라벨: {', '.join(MINORITY_CONFIG)}")

    existing_titles = load_existing_titles(LABELED_TITLES_CSV) if not args.overwrite else set()
    existing_counts = load_existing_label_counts(LABELED_TITLES_CSV) if not args.overwrite else Counter()

    print(f"기존 CSV: {len(existing_titles)}건")
    if existing_counts:
        ordered = dict(sorted(existing_counts.items(), key=lambda x: -x[1]))
        print(f"현재 분포: {ordered}")
    print(f"수집 대상 라벨: {', '.join(target_labels)}\n")

    all_rows: list[dict] = []
    for label in target_labels:
        rows = _run_label(
            label,
            MINORITY_CONFIG[label],
            per_keyword=args.per_keyword,
            existing_titles=existing_titles,
            existing_counts=existing_counts,
            dry_run=args.dry_run,
        )
        all_rows.extend(rows)
        existing_counts[label] += len(rows)

    if not all_rows:
        print("\n추가할 기사 없음")
        return

    if args.dry_run:
        print(f"\n[dry-run] 저장 건너뜀 (수집 {len(all_rows)}건)")
        return

    print(f"\n[저장] {LABELED_TITLES_CSV}")
    print_stats(all_rows)
    saved = write_csv(all_rows, LABELED_TITLES_CSV, append=not args.overwrite)
    print(f"\n저장 완료: {saved}건")


if __name__ == "__main__":
    main()
