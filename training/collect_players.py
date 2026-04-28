"""
선수 단위 뉴스 수집 파이프라인.

KBO 사이트에서 현재 롯데 엔트리를 수집하고,
선수별로 네이버 뉴스를 검색하여 라벨링 데이터를 생성한다.

팀 파이프라인(collect_for_labeling.py)과의 차이:
  - 검색 키워드 = 선수 이름
  - detected_players에 검색 선수가 항상 포함 보장
  - GPT 라벨링 시 "검색 선수: {이름}" 컨텍스트 제공
  - is_lotte_related 기본값 true (롯데 선수로 검색된 결과)

출력: training/data/labeled_players.csv

사용:
    cd lotte-insight
    python training/collect_players.py
    python training/collect_players.py --days 60
    python training/collect_players.py --no-label
    python training/collect_players.py --overwrite
    python training/collect_players.py --player 전준우   # 특정 선수만
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from collect_utils import (
    DATA_DIR,
    auto_label,
    fetch_naver,
    item_to_row,
    print_stats,
    write_csv,
)

OUTPUT_CSV = DATA_DIR / "labeled_players.csv"


def _get_roster(player_filter: str | None) -> list[str]:
    try:
        from batch.kbo_crawler import fetch_roster
        roster = fetch_roster()
        print(f"  KBO 엔트리 {len(roster)}명 수집 완료")
    except Exception as e:
        print(f"  [오류] KBO 엔트리 수집 실패: {e}")
        sys.exit(1)

    if player_filter:
        roster = [p for p in roster if p == player_filter]
        if not roster:
            print(f"  [오류] '{player_filter}' 선수를 엔트리에서 찾을 수 없습니다.")
            sys.exit(1)

    return roster


def collect_by_player(
    roster: list[str],
    days_cutoff: str | None,
) -> list[dict]:
    """
    선수별로 네이버 뉴스를 검색한다 (Naver API 최대 100건/쿼리).
    각 행에는 검색에 사용된 선수명(_search_player)이 임시 키로 기록된다.
    """
    seen: set[str] = set()
    rows: list[dict] = []

    for player in roster:
        keyword = f"롯데 {player}"
        print(f"  '{keyword}' ...", end=" ", flush=True)
        try:
            items = fetch_naver(keyword, display=100)
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
            row["_search_player"] = player
            rows.append(row)
            added += 1

        print(f"{added}건 추가 (누계 {len(rows)}건)")
        time.sleep(0.3)

    rows.sort(key=lambda r: r["published_at"], reverse=True)
    return rows


_LOTTE_KEYWORDS = {"롯데", "자이언츠", "사직", "LT"}


def _filter_lotte_related(rows: list[dict], labeled: bool) -> list[dict]:
    """
    수집된 행에서 롯데와 무관한 기사를 제거한다.

    labeled=True  : GPT가 설정한 is_lotte_related 값을 기준으로 판단
    labeled=False : 제목 + description에 롯데 관련 키워드 포함 여부로 판단
                    (--no-label 모드에서 "롯데 {선수명}" 검색을 통과한 타팀
                     동명이인 기사를 2차로 걸러냄)
    """
    before = len(rows)
    if labeled:
        filtered = [r for r in rows if str(r.get("is_lotte_related", "true")).lower() == "true"]
    else:
        def _has_lotte(row: dict) -> bool:
            text = row.get("title", "") + " " + row.get("description_snippet", "")
            return any(kw in text for kw in _LOTTE_KEYWORDS)
        filtered = [r for r in rows if _has_lotte(r)]

    removed = before - len(filtered)
    method = "GPT is_lotte_related" if labeled else "키워드"
    print(f"      [{method}] {removed}건 제외 → 잔여 {len(filtered)}건")
    return filtered


def main():
    parser = argparse.ArgumentParser(description="선수 단위 뉴스 수집 + GPT 라벨링")
    parser.add_argument("--days",      type=int,  default=None, help="최근 N일 이내 기사만")
    parser.add_argument("--no-label",  action="store_true",     help="라벨링 건너뜀 (수집만)")
    parser.add_argument("--overwrite", action="store_true",     help="CSV 초기화")
    parser.add_argument("--player",    type=str,  default=None, help="특정 선수만 수집 (이름 정확히)")
    args = parser.parse_args()

    cutoff = None
    if args.days:
        cutoff = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%dT%H:%M:%S")

    # 1. 엔트리 수집
    print("[1/5] KBO 엔트리 수집 (Playwright) ...")
    roster = _get_roster(args.player)
    print(f"      선수 {len(roster)}명 (선수당 Naver API 최대 100건)\n")

    # 2. 선수별 뉴스 수집
    print("[2/5] 선수별 뉴스 수집")
    rows = collect_by_player(roster, cutoff)
    print(f"      수집 완료: {len(rows)}건\n")

    # 3. GPT 라벨링
    if not args.no_label:
        print("[3/5] GPT 자동 라벨링")

        def extra_ctx(row: dict) -> str:
            return f"검색 선수: {row['_search_player']} (롯데 자이언츠 소속)"

        def ensure_players(row: dict) -> list[str]:
            return [row["_search_player"]]

        rows = auto_label(
            rows,
            extra_context_fn=extra_ctx,
            ensure_players_fn=ensure_players,
        )
        print_stats(rows)
    else:
        print("[3/5] 라벨링 건너뜀 (--no-label)")
        for row in rows:
            row["detected_players"] = row["_search_player"]
            row["is_lotte_related"] = "true"

    # 4. 롯데 관련성 보정
    print("\n[4/5] 롯데 관련성 보정")
    rows = _filter_lotte_related(rows, labeled=not args.no_label)

    # 5. CSV 저장 (_search_player는 내부용 임시 키, CSV에 기록하지 않음)
    print(f"\n[5/5] CSV 저장 → {OUTPUT_CSV}")
    saved = write_csv(rows, OUTPUT_CSV, append=not args.overwrite)
    print(f"      {saved}건 저장 완료")

    if not args.no_label:
        low_conf = [r for r in rows if r.get("confidence_score") and float(r["confidence_score"]) < 0.7]
        if low_conf:
            print(f"\n검수 권장: confidence < 0.7 항목 {len(low_conf)}건")


if __name__ == "__main__":
    main()
