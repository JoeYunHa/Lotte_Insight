"""GPT call failed 행을 재라벨링하는 스크립트."""

from __future__ import annotations

import csv
from pathlib import Path

from collect_utils import auto_label, write_csv
from settings import LABELED_TITLES_CSV, LABELED_PLAYERS_CSV


def relabel_failed(csv_path: Path) -> None:
    if not csv_path.exists():
        print(f"파일 없음: {csv_path}")
        return

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        all_rows = list(reader)

    failed_mask = [
        "GPT call failed" in row.get("confidence_note", "")
        for row in all_rows
    ]
    failed_rows = [row for row, is_failed in zip(all_rows, failed_mask) if is_failed]
    ok_rows = [row for row, is_failed in zip(all_rows, failed_mask) if not is_failed]

    print(f"{csv_path.name}: 전체 {len(all_rows)}건 중 재라벨링 대상 {len(failed_rows)}건")

    if not failed_rows:
        print("재라벨링 대상 없음.")
        return

    # 라벨 필드 초기화 후 auto_label 재호출
    for row in failed_rows:
        row["primary_label"] = ""
        row["secondary_labels"] = ""
        row["confidence_score"] = ""
        row["confidence_note"] = ""
        row["is_lotte_related"] = ""

    relabeled = auto_label(failed_rows)

    merged = ok_rows + relabeled
    merged.sort(key=lambda r: int(r.get("id") or 0))

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)

    still_failed = sum(
        1 for r in relabeled
        if "GPT call failed" in r.get("confidence_note", "") or r.get("confidence_score") == "0.0"
    )
    print(f"완료: {len(relabeled) - still_failed}건 성공, {still_failed}건 여전히 실패")


if __name__ == "__main__":
    import sys
    targets = sys.argv[1:] or ["titles"]
    for target in targets:
        if target == "titles":
            relabel_failed(LABELED_TITLES_CSV)
        elif target == "players":
            relabel_failed(LABELED_PLAYERS_CSV)
        else:
            relabel_failed(Path(target))
