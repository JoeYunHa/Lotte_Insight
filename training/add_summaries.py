"""Backfill structured summary fields for labeled article CSV rows."""

from __future__ import annotations

import argparse

from collect_utils import add_structured_summaries, load_csv_rows, rewrite_csv
from settings import LABELED_PLAYERS_CSV, LABELED_TITLES_CSV


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
    args = parser.parse_args()

    target_csv = _select_csv(args.dataset)
    rows = load_csv_rows(target_csv)
    if not rows:
        print(f"No rows found: {target_csv}")
        return

    rows = add_structured_summaries(rows, overwrite=args.overwrite)
    rewrite_csv(rows, target_csv)
    print(f"Saved structured summaries: {target_csv} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
