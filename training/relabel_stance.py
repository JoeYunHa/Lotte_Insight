"""lotte_stance 재라벨링 스크립트.

대상: primary_label == MATCH_RELATED AND lotte_stance == positive
      AND key_players에 롯데 선수가 없는 행 (상대팀 선수 활약 기사 오분류 수정).

수정된 SUMMARY_SYSTEM_PROMPT(collect_utils.py)를 사용해 event_summary/key_players/lotte_stance를
재생성하고 CSV를 덮어쓴다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from collect_utils import add_structured_summaries, load_csv_rows, rewrite_csv
from settings import LABELED_PLAYERS_CSV, LABELED_TITLES_CSV


# 롯데 선수 소속 판별: detected_players 컬럼은 player_catalog 매칭 결과이므로
# 값이 있으면 롯데 선수가 언급된 기사로 간주한다.
def _has_lotte_player(row: dict) -> bool:
    return bool(str(row.get("detected_players", "") or "").strip())


def _is_relabel_target(row: dict) -> bool:
    """재라벨링 대상 행 판별."""
    label = str(row.get("primary_label", "")).strip()
    stance = str(row.get("lotte_stance", "")).strip().lower()
    if label != "MATCH_RELATED" or stance != "positive":
        return False
    # 롯데 선수가 감지됐으면 positive가 맞을 수 있으므로 제외
    if _has_lotte_player(row):
        return False
    return True


def relabel_stance(csv_path: Path, *, dry_run: bool = False) -> None:
    if not csv_path.exists():
        print(f"파일 없음: {csv_path}")
        return

    rows = load_csv_rows(csv_path)
    total = len(rows)

    target_indexes = [i for i, row in enumerate(rows) if _is_relabel_target(row)]
    print(f"{csv_path.name}: 전체 {total}건 중 재라벨링 대상 {len(target_indexes)}건")

    if not target_indexes:
        print("재라벨링 대상 없음.")
        return

    # 대상 행 미리보기
    print("\n[대상 행 샘플 (최대 10건)]")
    for i in target_indexes[:10]:
        row = rows[i]
        print(
            f"  id={row.get('id'):>5}  stance={row.get('lotte_stance'):<8}"
            f"  key_players={row.get('key_players'):<30}"
            f"  title={row.get('title', '')[:50]}"
        )

    if dry_run:
        print("\n--dry-run 모드: CSV 변경 없이 종료합니다.")
        return

    # 대상 행의 요약 필드 초기화 후 재생성
    for i in target_indexes:
        rows[i]["event_summary"] = ""
        rows[i]["lotte_stance"] = ""
        rows[i]["key_players"] = ""
        rows[i]["game_ref"] = ""

    # add_structured_summaries는 event_summary가 비어 있는 행만 처리(overwrite=False)
    rows = add_structured_summaries(rows, overwrite=False)

    rewrite_csv(rows, csv_path)

    changed = sum(
        1 for i in target_indexes
        if str(rows[i].get("lotte_stance", "")).strip() != "positive"
    )
    still_positive = len(target_indexes) - changed
    print(f"\n완료: {changed}건 변경, {still_positive}건 여전히 positive")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MATCH_RELATED+positive 행 중 롯데 선수 미감지 행의 lotte_stance를 재라벨링."
    )
    parser.add_argument(
        "--dataset",
        choices=("titles", "players", "both"),
        default="both",
        help="대상 CSV (기본값: both)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="직접 CSV 경로 지정 (--dataset 무시)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="대상 행만 출력하고 CSV는 변경하지 않음",
    )
    args = parser.parse_args()

    if args.csv:
        relabel_stance(args.csv, dry_run=args.dry_run)
        return

    targets: list[Path] = []
    if args.dataset in ("titles", "both"):
        targets.append(LABELED_TITLES_CSV)
    if args.dataset in ("players", "both"):
        targets.append(LABELED_PLAYERS_CSV)

    for csv_path in targets:
        relabel_stance(csv_path, dry_run=args.dry_run)
        print()


if __name__ == "__main__":
    main()
