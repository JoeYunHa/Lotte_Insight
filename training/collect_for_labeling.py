"""Collect team-level news data for labeling."""

from __future__ import annotations

import argparse

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
from settings import (
    DEFAULT_LABELING_COUNT,
    FOCUS_LABEL_KEYWORDS,
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
    return [row for row in rows if not row.get("title", "").startswith(PHOTO_PREFIXES)]


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
        help="Comma-separated labels to prioritize, e.g. CLUB_OPERATION,INTERVIEW,PLAYER_RELATED",
    )
    parser.add_argument(
        "--focus-only",
        action="store_true",
        help="Collect only focus-label keywords instead of the full team keyword set",
    )
    parser.add_argument("--no-label", action="store_true", help="Skip GPT labeling")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output CSV")
    args = parser.parse_args()

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
