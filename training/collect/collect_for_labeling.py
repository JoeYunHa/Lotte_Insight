"""Collect team-level news data for labeling."""

from __future__ import annotations

import argparse

from collect.collect_utils import (
    CHEERLEADER_KEYWORDS,
    RSS_TRAINING_FEEDS,
    add_structured_summaries,
    apply_label_cap,
    auto_label,
    build_days_cutoff,
    collect_news_by_keywords,
    collect_news_from_rss,
    fetch_google_news_rss_query,
    load_csv_rows,
    load_existing_label_counts,
    load_existing_titles,
    print_stats,
    rewrite_csv,
    write_csv,
)
from settings import (
    DEFAULT_LABELING_COUNT,
    FOCUS_LABEL_KEYWORDS,
    GAME_RESULTS_CSV,
    LABELED_TITLES_CSV,
    NAVER_DISPLAY_LIMIT,
    NAVER_MAX_START,
    TEAM_SEARCH_KEYWORDS,
)

DEFAULT_LABEL_CAP = 250
PHOTO_PREFIXES = ("[포토", "[사진")


def build_keywords(focus_labels: list[str], focus_only: bool) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()

    if not focus_only:
        for keyword in TEAM_SEARCH_KEYWORDS:
            if keyword not in seen:
                keywords.append(keyword)
                seen.add(keyword)

    for label in focus_labels:
        for keyword in FOCUS_LABEL_KEYWORDS.get(label, []):
            if keyword not in seen:
                keywords.append(keyword)
                seen.add(keyword)

    return keywords


def collect(
    target_count: int,
    days_cutoff: str | None,
    per_keyword: int,
    existing_titles: set[str],
    keywords: list[str],
) -> list[dict]:
    return collect_news_by_keywords(
        keywords,
        days_cutoff=days_cutoff,
        target_count=target_count,
        per_keyword_limit=per_keyword,
        existing_titles=existing_titles,
    )


def parse_focus_labels(raw: str) -> list[str]:
    labels = [label.strip() for label in raw.split(",") if label.strip()]
    invalid = [label for label in labels if label not in FOCUS_LABEL_KEYWORDS]
    if invalid:
        raise SystemExit(f"Unsupported focus labels: {', '.join(invalid)}")
    return labels


def filter_rows_by_primary_labels(rows: list[dict], labels: list[str]) -> list[dict]:
    if not labels:
        return rows
    allowed = set(labels)
    return [row for row in rows if row.get("primary_label") in allowed]





def filter_photo_captions(rows: list[dict]) -> list[dict]:
    return [
        row for row in rows
        if not row.get("title", "").startswith(PHOTO_PREFIXES)
        and not any(kw in row.get("title", "") for kw in CHEERLEADER_KEYWORDS)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect team news and auto-label it.")
    parser.add_argument("--count", type=int, default=DEFAULT_LABELING_COUNT, help="Target article count")
    parser.add_argument("--days", type=int, default=None, help="Only collect articles from the last N days")
    parser.add_argument(
        "--per-keyword",
        type=int,
        default=NAVER_DISPLAY_LIMIT,
        help=f"Maximum items per keyword (1-{NAVER_MAX_START})",
    )
    parser.add_argument(
        "--label-cap",
        type=int,
        default=DEFAULT_LABEL_CAP,
        help="Maximum cumulative rows per primary label in the output CSV (0 disables capping)",
    )
    parser.add_argument(
        "--focus-labels",
        type=str,
        default="",
        help="Comma-separated labels to prioritize, e.g. CLUB_OPERATION,INTERVIEW,PERFORMANCE_ANALYSIS",
    )
    parser.add_argument(
        "--focus-only",
        action="store_true",
        help="Collect only focus-label keywords instead of the full team keyword set",
    )
    parser.add_argument("--no-label", action="store_true", help="Skip GPT labeling")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output CSV")
    parser.add_argument(
        "--rss",
        action="store_true",
        help="표준 RSS 피드 전체(Google News + 스포츠경향 + 연합뉴스 + 동아)에서 추가 수집",
    )
    parser.add_argument(
        "--rss-query",
        type=str,
        default="",
        help="Google News RSS 커스텀 쿼리 (쉼표 구분, 예: 롯데관전평,롯데 직관)",
    )
    parser.add_argument(
        "--add-summaries",
        action="store_true",
        help="기존 CSV에서 event_summary 없는 행에 GPT 요약을 채운다 (새 수집 없이 단독 실행 가능)",
    )
    args = parser.parse_args()

    # --add-summaries 단독 실행: 기존 CSV event_summary 백필 후 종료
    if args.add_summaries:
        if not LABELED_TITLES_CSV.exists():
            print(f"[ERROR] {LABELED_TITLES_CSV} 없음")
            return
        if not GAME_RESULTS_CSV.exists():
            print(f"[WARN] game_results.csv 없음: {GAME_RESULTS_CSV}")
            print("       game_context가 '해당 날짜 경기 없음'으로 채워집니다.")
            print("       먼저 collect_game_results.py를 실행하세요.")
            print()
        rows = load_csv_rows(LABELED_TITLES_CSV)
        missing = sum(1 for r in rows if not str(r.get("event_summary", "")).strip())
        print(f"기존 CSV: {len(rows)}행  event_summary 없음: {missing}행")
        if missing == 0:
            print("모든 행에 event_summary 있음 — 종료")
            return
        rows = add_structured_summaries(rows)
        saved = rewrite_csv(rows, LABELED_TITLES_CSV)
        print(f"백필 완료: {saved}행 저장")
        return

    cutoff = build_days_cutoff(args.days)
    per_keyword = max(1, min(args.per_keyword, NAVER_MAX_START))
    focus_labels = parse_focus_labels(args.focus_labels)
    keywords = build_keywords(focus_labels, args.focus_only)

    existing_titles = load_existing_titles(LABELED_TITLES_CSV) if not args.overwrite else set()
    existing_label_counts = load_existing_label_counts(LABELED_TITLES_CSV) if not args.overwrite else {}

    print(f"Existing CSV rows: {len(existing_titles)}")
    if existing_label_counts:
        ordered = {k: v for k, v in sorted(existing_label_counts.items(), key=lambda item: -item[1])}
        print(f"Existing label counts: {ordered}")
    if focus_labels:
        print(f"Focus labels: {', '.join(focus_labels)}")
    print(f"Keyword count: {len(keywords)}")

    print(f"\n[1/3] Collect team news - target {args.count}, per-keyword {per_keyword}")
    rows = collect(args.count, cutoff, per_keyword, existing_titles, keywords)
    before_photo_filter = len(rows)
    rows = filter_photo_captions(rows)
    if len(rows) != before_photo_filter:
        print(f"Removed photo-caption rows: {before_photo_filter - len(rows)}")
    print(f"Collected rows: {len(rows)}")

    if args.rss:
        merged_existing = existing_titles | {r["title"] for r in rows}
        print("\n[RSS] 표준 피드 수집")
        rss_rows = collect_news_from_rss(merged_existing)
        rss_rows = filter_photo_captions(rss_rows)
        print(f"RSS 수집 합계: {len(rss_rows)}건")
        rows.extend(rss_rows)

    if args.rss_query:
        queries = [q.strip() for q in args.rss_query.split(",") if q.strip()]
        merged_existing = existing_titles | {r["title"] for r in rows}
        print(f"\n[RSS Query] 쿼리: {queries}")
        q_rows = fetch_google_news_rss_query(queries, merged_existing)
        q_rows = filter_photo_captions(q_rows)
        print(f"RSS Query 수집: {len(q_rows)}건")
        rows.extend(q_rows)

    if not rows:
        print("No new articles were collected.")
        return

    if not args.no_label:
        print("[2/3] GPT auto-labeling")
        rows = auto_label(rows)
        print_stats(rows)

        if focus_labels:
            before = len(rows)
            rows = filter_rows_by_primary_labels(rows, focus_labels)
            print(f"Filtered to focus labels: kept {len(rows)} of {before}")

        if args.label_cap > 0:
            rows, discarded = apply_label_cap(rows, existing_label_counts, args.label_cap)
            if discarded:
                print(f"Applied label cap {args.label_cap}: discarded {discarded}, kept {len(rows)}")
    else:
        print("[2/3] Skip labeling (--no-label)")

    print(f"\n[3/3] Save CSV -> {LABELED_TITLES_CSV}")
    saved = write_csv(rows, LABELED_TITLES_CSV, append=not args.overwrite)
    print(f"Saved rows: {saved}")


if __name__ == "__main__":
    main()
