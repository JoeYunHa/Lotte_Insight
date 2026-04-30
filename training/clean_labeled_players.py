"""Clean and review suspicious rows in labeled_players.csv."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from settings import LABELED_PLAYERS_CSV, ROOT_DIR

REVIEW_COLUMNS = [
    "review_flags",
    "suggested_action",
    "clean_detected_players",
]

ARTIFACTS_DIR = ROOT_DIR / "artifacts"

TEAM_KEYWORDS = (
    "롯데",
    "자이언츠",
    "사직",
    "거인",
    "부산",
)

BASEBALL_KEYWORDS = (
    "야구",
    "프로야구",
    "kbo",
    "투수",
    "타자",
    "포수",
    "감독",
    "코치",
    "선발",
    "불펜",
    "마운드",
    "라인업",
    "등판",
    "말소",
    "등록",
    "복귀",
    "부상",
    "경기",
    "승리",
    "패배",
    "연패",
    "안타",
    "홈런",
    "타점",
    "세이브",
    "이닝",
    "타율",
    "ops",
    "era",
    "whip",
)

NON_BASEBALL_KEYWORDS = (
    "금리",
    "이자비용",
    "비우량",
    "합병",
    "주가",
    "증권",
    "시장",
    "의원",
    "무공천",
    "정당",
    "라디오",
    "후원",
    "예술",
    "출시",
    "브랜드",
)

PHOTO_TITLE_PREFIXES = (
    "[사진]",
    "[포토]",
)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def save_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_bool(value: str) -> str:
    return str(value or "").strip().lower()


def split_players(value: str) -> list[str]:
    players: list[str] = []
    for player in str(value or "").split(";"):
        player = player.strip()
        if player and player not in players:
            players.append(player)
    return players


def scrub_detected_players(row: dict[str, str]) -> list[str]:
    text = f"{row.get('title', '')} {row.get('description_snippet', '')}"
    return [player for player in split_players(row.get("detected_players", "")) if player in text]


def has_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def classify_row(row: dict[str, str]) -> tuple[list[str], str, list[str]]:
    text = f"{row.get('title', '')} {row.get('description_snippet', '')}".strip()
    clean_players = scrub_detected_players(row)
    flags: list[str] = []

    has_team = has_any_keyword(text, TEAM_KEYWORDS)
    has_baseball = has_any_keyword(text, BASEBALL_KEYWORDS)
    has_non_baseball = has_any_keyword(text, NON_BASEBALL_KEYWORDS)
    is_photo = row.get("title", "").startswith(PHOTO_TITLE_PREFIXES)
    primary_label = row.get("primary_label", "")

    if not clean_players and split_players(row.get("detected_players", "")):
        flags.append("detected_players_not_in_text")
    if primary_label == "ETC":
        flags.append("etc_label")
    if not has_baseball:
        flags.append("missing_baseball_keywords")
    if not has_team:
        flags.append("missing_team_keywords")
    if has_non_baseball and not has_baseball:
        flags.append("non_baseball_topic")
    if is_photo:
        flags.append("photo_caption")
    if normalize_bool(row.get("is_lotte_related", "")) != "true":
        flags.append("unexpected_not_lotte")

    if "non_baseball_topic" in flags:
        action = "drop"
    elif "detected_players_not_in_text" in flags or "etc_label" in flags:
        action = "review"
    elif "photo_caption" in flags and primary_label == "INTERVIEW":
        action = "review"
    else:
        action = "keep"

    return flags, action, clean_players


def build_outputs(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], Counter[str]]:
    cleaned_rows: list[dict[str, str]] = []
    review_rows: list[dict[str, str]] = []
    action_counts: Counter[str] = Counter()

    for row in rows:
        flags, action, clean_players = classify_row(row)
        action_counts[action] += 1

        cleaned = dict(row)
        cleaned["detected_players"] = ";".join(clean_players)
        cleaned_rows.append(cleaned)

        if action != "keep":
            review_row = dict(row)
            review_row["review_flags"] = ";".join(flags)
            review_row["suggested_action"] = action
            review_row["clean_detected_players"] = ";".join(clean_players)
            review_rows.append(review_row)

    return cleaned_rows, review_rows, action_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean and review labeled_players.csv")
    parser.add_argument("--input", type=Path, default=LABELED_PLAYERS_CSV)
    parser.add_argument("--cleaned-output", type=Path, default=ARTIFACTS_DIR / "labeled_players.cleaned.csv")
    parser.add_argument("--review-output", type=Path, default=ARTIFACTS_DIR / "labeled_players.review.csv")
    parser.add_argument("--apply-drop", action="store_true", help="Drop rows flagged with suggested_action=drop")
    args = parser.parse_args()

    rows = load_rows(args.input)
    cleaned_rows, review_rows, action_counts = build_outputs(rows)

    rows_to_save = cleaned_rows
    if args.apply_drop:
        drop_ids = {row["id"] for row in review_rows if row["suggested_action"] == "drop"}
        rows_to_save = [row for row in cleaned_rows if row.get("id") not in drop_ids]

    base_fieldnames = list(rows[0].keys()) if rows else []
    save_rows(args.cleaned_output, rows_to_save, base_fieldnames)
    save_rows(args.review_output, review_rows, base_fieldnames + REVIEW_COLUMNS)

    print(f"Input rows: {len(rows)}")
    print(f"Cleaned rows written: {len(rows_to_save)} -> {args.cleaned_output}")
    print(f"Review rows written: {len(review_rows)} -> {args.review_output}")
    for action in ("keep", "review", "drop"):
        print(f"  {action:<6} {action_counts.get(action, 0)}")


if __name__ == "__main__":
    main()
