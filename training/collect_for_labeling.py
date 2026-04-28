"""
팀 단위 뉴스 수집 파이프라인.
키워드: "롯데 자이언츠" (팀 전체 관련 기사)
출력: training/data/labeled_titles.csv

사용:
    cd lotte-insight
    python training/collect_for_labeling.py
    python training/collect_for_labeling.py --count 500 --days 60
    python training/collect_for_labeling.py --no-label   # 수집만
    python training/collect_for_labeling.py --overwrite  # CSV 초기화
"""

import argparse
import time
from pathlib import Path

import requests

from collect_utils import (
    DATA_DIR,
    auto_label,
    fetch_naver,
    item_to_row,
    parse_pub_date,
    print_stats,
    write_csv,
)

OUTPUT_CSV = DATA_DIR / "labeled_titles.csv"

_TEAM_KEYWORDS = [
    "롯데 자이언츠",
    "롯데 자이언츠 경기",
    "롯데 자이언츠 부상",
    "롯데 자이언츠 트레이드",
    "롯데 자이언츠 선발",
    "롯데 자이언츠 콜업",
]


def collect(target_count: int, days_cutoff: str | None) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []

    for keyword in _TEAM_KEYWORDS:
        if len(rows) >= target_count:
            break

        print(f"  '{keyword}' ...", end=" ", flush=True)
        try:
            items = fetch_naver(keyword)
        except requests.RequestException as e:
            print(f"실패 ({e})")
            continue

        added = 0
        for item in items:
            row = item_to_row(item)
            url = row.pop("_url")
            if not url or url in seen:
                continue
            if days_cutoff and row["published_at"] < days_cutoff:
                continue
            seen.add(url)
            rows.append(row)
            added += 1

        print(f"{added}건 추가 (누계 {len(rows)}건)")
        time.sleep(0.3)

    rows.sort(key=lambda r: r["published_at"], reverse=True)
    return rows[:target_count]


def main():
    parser = argparse.ArgumentParser(description="팀 단위 뉴스 수집 + GPT 라벨링")
    parser.add_argument("--count",     type=int,  default=300)
    parser.add_argument("--days",      type=int,  default=None, help="최근 N일 이내 기사만")
    parser.add_argument("--no-label",  action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    from datetime import datetime, timedelta
    cutoff = None
    if args.days:
        cutoff = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%S")

    print(f"[1/3] 팀 기사 수집 — 목표 {args.count}건")
    rows = collect(args.count, cutoff)
    print(f"      수집 완료: {len(rows)}건\n")

    if not args.no_label:
        print("[2/3] GPT 자동 라벨링")
        rows = auto_label(rows)
        print_stats(rows)
    else:
        print("[2/3] 라벨링 건너뜀 (--no-label)")

    print(f"\n[3/3] CSV 저장 → {OUTPUT_CSV}")
    saved = write_csv(rows, OUTPUT_CSV, append=not args.overwrite)
    print(f"      {saved}건 저장 완료")


if __name__ == "__main__":
    main()
