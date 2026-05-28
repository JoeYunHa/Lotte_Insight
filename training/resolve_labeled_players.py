"""Resolve reviewed rows from labeled_players.csv with deterministic heuristics."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from training.collect.clean_labeled_players import (
    ARTIFACTS_DIR,
    build_outputs,
    load_rows,
)
from settings import LABELED_PLAYERS_CSV

RESOLUTION_COLUMNS = [
    "resolution_action",
    "resolution_primary_label",
    "resolution_secondary_labels",
    "resolution_reason",
]

MATCH_PATTERNS = (
    "경기",
    "선발",
    "라인업",
    "승리",
    "패배",
    "연승",
    "연패",
    "스윕",
    "역전",
    "연장",
    "중계",
    "예매",
    "일정",
    "오늘의 경기",
)

INTERVIEW_PATTERNS = (
    "감독",
    "인터뷰",
    "현장",
    "소감",
    "말했다",
    "밝혔다",
    "극찬",
    "칭찬",
    "사령탑",
    "\"",
    "'",
)

CLUB_PATTERNS = (
    "마케팅",
    "행사",
    "티켓",
    "굿즈",
    "시구",
    "먹거리",
    "팬미팅",
    "은퇴식",
    "창단",
    "김장",
)

PERFORMANCE_PATTERNS = (
    "분석",
    "부진",
    "반등",
    "불안",
    "타율",
    "ops",
    "era",
    "whip",
    "기록",
    "순위",
    "지표",
    "첫 승",
    "호투",
    "부활",
    "병살",
    "불펜",
    "타선",
    "수비",
)

NON_BASEBALL_PATTERNS = (
    "롯데칠성",
    "롯데건설",
    "롯데컬처웍스",
    "롯데시네마",
    "롯데쇼핑",
    "이자비용",
    "금리",
    "증권",
    "브랜드",
    "출시",
    "광고",
    "e스포츠",
    "게임·IT",
)

SCORE_REGEX = re.compile(r"\b\d+\s*[-:대]\s*\d+\b")


def contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def resolve_etc_row(row: dict[str, str], clean_players: list[str]) -> tuple[str, str, str]:
    text = f"{row.get('title', '')} {row.get('description_snippet', '')}"

    if contains_any(text, NON_BASEBALL_PATTERNS):
        return "drop", "", "non_baseball_etc"
    if SCORE_REGEX.search(text) or contains_any(text, MATCH_PATTERNS):
        return "resolved", "MATCH_RELATED", "match_pattern"
    if contains_any(text, INTERVIEW_PATTERNS):
        return "resolved", "INTERVIEW", "interview_pattern"
    if contains_any(text, CLUB_PATTERNS):
        return "resolved", "CLUB_OPERATION", "club_pattern"
    if contains_any(text, PERFORMANCE_PATTERNS):
        return "resolved", "PERFORMANCE_ANALYSIS", "performance_pattern"
    return "manual_review", "", "unresolved_etc"


def resolve_review_row(row: dict[str, str]) -> tuple[dict[str, str], bool]:
    review_flags = set(filter(None, str(row.get("review_flags", "")).split(";")))
    clean_players = [player for player in str(row.get("clean_detected_players", "")).split(";") if player]

    resolved = dict(row)
    resolved["detected_players"] = ";".join(clean_players)
    resolved["resolution_action"] = "manual_review"
    resolved["resolution_primary_label"] = ""
    resolved["resolution_secondary_labels"] = ""
    resolved["resolution_reason"] = "no_rule"

    if row.get("suggested_action") == "drop" or "non_baseball_topic" in review_flags:
        resolved["resolution_action"] = "drop"
        resolved["resolution_reason"] = "clean_drop_rule"
        return resolved, False

    if "photo_caption" in review_flags:
        resolved["resolution_action"] = "drop"
        resolved["resolution_reason"] = "photo_caption"
        return resolved, False

    if "detected_players_not_in_text" in review_flags and row.get("primary_label") != "ETC":
        resolved["resolution_action"] = "resolved"
        resolved["resolution_primary_label"] = row.get("primary_label", "")
        resolved["resolution_secondary_labels"] = row.get("secondary_labels", "")
        resolved["resolution_reason"] = "drop_ghost_players_only"
        return resolved, True

    if row.get("primary_label") == "ETC":
        action, label, reason = resolve_etc_row(row, clean_players)
        resolved["resolution_action"] = action
        resolved["resolution_primary_label"] = label
        resolved["resolution_reason"] = reason
        if action == "resolved":
            resolved["resolution_secondary_labels"] = ""
            return resolved, True
        return resolved, False

    text = f"{row.get('title', '')} {row.get('description_snippet', '')}"
    if contains_any(text, NON_BASEBALL_PATTERNS):
        resolved["resolution_action"] = "drop"
        resolved["resolution_reason"] = "non_baseball_orig"
        return resolved, False

    resolved["resolution_action"] = "resolved"
    resolved["resolution_primary_label"] = row.get("primary_label", "")
    resolved["resolution_secondary_labels"] = row.get("secondary_labels", "")
    resolved["resolution_reason"] = "keep_cleaned_players"
    return resolved, True


def save_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve reviewed labeled_players rows")
    parser.add_argument("--input", type=Path, default=LABELED_PLAYERS_CSV)
    parser.add_argument(
        "--resolved-output",
        type=Path,
        default=ARTIFACTS_DIR / "labeled_players.resolved.csv",
    )
    parser.add_argument(
        "--manual-review-output",
        type=Path,
        default=ARTIFACTS_DIR / "labeled_players.manual_review.csv",
    )
    parser.add_argument(
        "--review-log-output",
        type=Path,
        default=ARTIFACTS_DIR / "labeled_players.review_resolutions.csv",
    )
    args = parser.parse_args()

    source_rows = load_rows(args.input)
    cleaned_rows, review_rows, _action_counts = build_outputs(source_rows)
    cleaned_by_id = {row["id"]: row for row in cleaned_rows}

    resolved_rows: list[dict[str, str]] = []
    manual_review_rows: list[dict[str, str]] = []
    review_log_rows: list[dict[str, str]] = []
    drop_ids: set[str] = set()

    for review_row in review_rows:
        resolved_review, keep_row = resolve_review_row(review_row)
        review_log_rows.append(resolved_review)

        row_id = resolved_review["id"]
        if resolved_review["resolution_action"] == "drop":
            drop_ids.add(row_id)
            continue

        if resolved_review["resolution_action"] == "manual_review":
            manual_review_rows.append(resolved_review)
            continue

        cleaned = dict(cleaned_by_id[row_id])
        cleaned["detected_players"] = resolved_review.get("clean_detected_players", cleaned.get("detected_players", ""))
        cleaned["primary_label"] = resolved_review["resolution_primary_label"] or cleaned.get("primary_label", "")
        cleaned["secondary_labels"] = (
            resolved_review["resolution_secondary_labels"]
            if resolved_review["resolution_secondary_labels"] != ""
            else cleaned.get("secondary_labels", "")
        )
        cleaned["confidence_note"] = resolved_review["resolution_reason"]
        resolved_rows.append(cleaned)

    resolved_ids = {row["id"] for row in resolved_rows}
    for row in cleaned_rows:
        row_id = row["id"]
        if row_id in drop_ids or row_id in resolved_ids:
            continue
        resolved_rows.append(row)

    # 모든 resolved 행에 대해 비야구 패턴 최종 필터 (orig 행 포함)
    non_baseball_dropped = 0
    filtered_rows: list[dict[str, str]] = []
    for row in resolved_rows:
        text = f"{row.get('title', '')} {row.get('description_snippet', '')}"
        if contains_any(text, NON_BASEBALL_PATTERNS):
            non_baseball_dropped += 1
        else:
            filtered_rows.append(row)
    resolved_rows = filtered_rows

    base_fieldnames = list(cleaned_rows[0].keys()) if cleaned_rows else []
    review_fieldnames = list(review_log_rows[0].keys()) if review_log_rows else base_fieldnames + RESOLUTION_COLUMNS

    save_rows(args.resolved_output, resolved_rows, base_fieldnames)
    save_rows(args.manual_review_output, manual_review_rows, review_fieldnames)
    save_rows(args.review_log_output, review_log_rows, review_fieldnames)

    print(f"Source rows: {len(source_rows)}")
    print(f"Reviewed rows: {len(review_rows)}")
    print(f"Non-baseball dropped (final pass): {non_baseball_dropped}")
    print(f"Resolved output: {len(resolved_rows)} -> {args.resolved_output}")
    print(f"Manual review remaining: {len(manual_review_rows)} -> {args.manual_review_output}")
    print(f"Review log rows: {len(review_log_rows)} -> {args.review_log_output}")


if __name__ == "__main__":
    main()
