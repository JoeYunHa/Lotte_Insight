"""Backfill structured summary fields for labeled article CSV rows."""

from __future__ import annotations

import argparse

from collect.collect_utils import add_player_stances, add_structured_summaries, load_csv_rows, rewrite_csv
from settings import GAME_RESULTS_CSV, LABELED_PLAYERS_CSV, LABELED_TITLES_CSV


def _select_csv(dataset: str):
    if dataset == "titles":
        return LABELED_TITLES_CSV
    if dataset == "players":
        return LABELED_PLAYERS_CSV
    raise ValueError(f"Unsupported dataset: {dataset}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate structured summary fields for labeled CSV rows.")
    parser.add_argument(
        "--dataset",
        choices=("titles", "players"),
        default="titles",
        help="Target labeled CSV dataset",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate summaries even when event_summary is already present",
    )
    parser.add_argument(
        "--player-stance-only",
        action="store_true",
        help=(
            "labeled_players.csv 전용: event_summary는 유지하고 player_stance만 생성. "
            "query_player가 key_players에 포함된 행에만 적용. --dataset players와 함께 사용."
        ),
    )
    args = parser.parse_args()

    if args.player_stance_only and args.dataset != "players":
        print("[ERROR] --player-stance-only는 --dataset players와 함께만 사용 가능합니다.")
        return

    if not GAME_RESULTS_CSV.exists():
        print(f"[WARN] game_results.csv 없음: {GAME_RESULTS_CSV}")
        print("       game_context가 '해당 날짜 경기 없음'으로 채워집니다.")
        print("       먼저 collect_game_results.py를 실행하세요.")
        print()
    else:
        import csv
        with GAME_RESULTS_CSV.open(encoding="utf-8-sig") as f:
            row_count = sum(1 for _ in csv.reader(f)) - 1
        print(f"game_results.csv: {row_count}경기 로드됨")

    target_csv = _select_csv(args.dataset)
    rows = load_csv_rows(target_csv)
    if not rows:
        print(f"No rows found: {target_csv}")
        return

    if args.player_stance_only:
        rows = add_player_stances(rows)
    else:
        rows = add_structured_summaries(rows, overwrite=args.overwrite)

    rewrite_csv(rows, target_csv)
    print(f"Saved: {target_csv} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
