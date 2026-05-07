"""Collect minority-class articles with per-label day windows and focus-only keywords."""

from __future__ import annotations

import argparse
from collections import Counter

from collect_for_labeling import build_keywords, filter_photo_captions, filter_rows_by_primary_labels
from collect_utils import (
    apply_label_cap,
    auto_label,
    build_days_cutoff,
    collect_news_by_keywords,
    load_existing_label_counts,
    load_existing_titles,
    print_stats,
    write_csv,
)
from settings import LABELED_TITLES_CSV, NAVER_DISPLAY_LIMIT

# 라벨별 수집 설정: days=조회 기간, count=수집 목표, cap=CSV 누적 상한
MINORITY_CONFIG: dict[str, dict] = {
    "INTERVIEW":            {"days": 30,  "count": 200, "cap": 200},
    "CLUB_OPERATION":       {"days": 90,  "count": 150, "cap": 150},
    "TRANSACTION_CONTRACT": {"days": 180, "count": 200, "cap": 200},
    "PERFORMANCE_ANALYSIS": {"days": 60,  "count": 200, "cap": 250},
}


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

    rows = auto_label(rows)
    rows = filter_rows_by_primary_labels(rows, [label])
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
        default=NAVER_DISPLAY_LIMIT,
        help="키워드당 최대 수집 건수",
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
