"""Review and apply corrections for is_lotte_related labels."""

import argparse
import csv
import sys
import time

from openai_utils import chat_json, require_openai_api_key
from settings import (
    AUTO_LABEL_SLEEP_SECONDS,
    LABELED_TITLES_CSV,
    OPENAI_MODEL,
    REVIEW_LOTTE_RELATED_CSV,
    TEAM_FULL_NAME_KO,
)

REVIEW_HEADERS = [
    "id",
    "title",
    "description_snippet",
    "source_name",
    "published_at",
    "primary_label",
    "original_value",
    "gpt_value",
    "gpt_reason",
    "corrected_value",
]

REVIEW_SYSTEM_PROMPT = f"""당신은 KBO 뉴스 기사와 {TEAM_FULL_NAME_KO}의 관련성을 판별하는 전문가입니다.

## is_lotte_related 판단 기준
- true: {TEAM_FULL_NAME_KO} 소속 선수, 구단, 경기 자체가 기사 주체
- false: {TEAM_FULL_NAME_KO}가 상대팀 또는 단순 언급 수준

## 출력 형식
{{
  "is_lotte_related": true 또는 false,
  "reason": "판단 근거"
}}"""


def _call_gpt(title: str, description: str) -> dict:
    user_content = f"제목: {title}"
    if description:
        user_content += f"\ndescription: {description}"
    return chat_json(REVIEW_SYSTEM_PROMPT, user_content, max_tokens=100)


def run_review(review_all: bool) -> None:
    require_openai_api_key()

    if not LABELED_TITLES_CSV.exists():
        print(f"[ERROR] {LABELED_TITLES_CSV} 파일이 없습니다.")
        sys.exit(1)

    with LABELED_TITLES_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    if review_all:
        candidates = rows
        print(f"전체 재평가 모드 - {len(candidates)}건")
    else:
        candidates = [row for row in rows if row.get("is_lotte_related", "").strip().lower() == "true"]
        print(f"is_lotte_related=true 항목만 재평가 - {len(candidates)}건")

    if not candidates:
        print("재평가 대상이 없습니다.")
        return

    flagged: list[dict] = []
    fail = 0

    for index, row in enumerate(candidates, start=1):
        try:
            result = _call_gpt(row["title"], row["description_snippet"])
            gpt_value = str(result.get("is_lotte_related", True)).lower()
            gpt_reason = result.get("reason", "")
        except Exception as exc:
            gpt_value = row.get("is_lotte_related", "true").lower()
            gpt_reason = f"GPT 호출 실패: {exc}"
            fail += 1

        original = row.get("is_lotte_related", "true").strip().lower()
        if gpt_value != original:
            flagged.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "description_snippet": row["description_snippet"],
                    "source_name": row["source_name"],
                    "published_at": row["published_at"],
                    "primary_label": row["primary_label"],
                    "original_value": original,
                    "gpt_value": gpt_value,
                    "gpt_reason": gpt_reason,
                    "corrected_value": "",
                }
            )

        if index % 50 == 0 or index == len(candidates):
            pct = index / len(candidates) * 100
            print(f"  [{index:>4}/{len(candidates)}] {pct:5.1f}%  불일치 {len(flagged)}건  실패 {fail}건")

        time.sleep(AUTO_LABEL_SLEEP_SECONDS)

    print(f"\n재평가 완료 - 불일치 {len(flagged)}건 / 전체 {len(candidates)}건 (모델: {OPENAI_MODEL})")

    if not flagged:
        print("불일치 항목이 없습니다. review CSV를 생성하지 않습니다.")
        return

    REVIEW_LOTTE_RELATED_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_LOTTE_RELATED_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_HEADERS)
        writer.writeheader()
        writer.writerows(flagged)

    print(f"저장 완료: {REVIEW_LOTTE_RELATED_CSV}")


def run_apply() -> None:
    if not REVIEW_LOTTE_RELATED_CSV.exists():
        print(f"[ERROR] {REVIEW_LOTTE_RELATED_CSV} 파일이 없습니다. 먼저 재평가를 실행하세요.")
        sys.exit(1)

    if not LABELED_TITLES_CSV.exists():
        print(f"[ERROR] {LABELED_TITLES_CSV} 파일이 없습니다.")
        sys.exit(1)

    with REVIEW_LOTTE_RELATED_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        review_rows = list(csv.DictReader(file))

    corrections: dict[str, str] = {}
    for row in review_rows:
        final_value = row["corrected_value"].strip().lower()
        if final_value not in ("true", "false"):
            final_value = row["gpt_value"].strip().lower()
        if final_value in ("true", "false"):
            corrections[row["id"]] = final_value

    if not corrections:
        print("적용할 수정값이 없습니다.")
        return

    with LABELED_TITLES_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        main_rows = list(csv.DictReader(file))

    changed = 0
    for row in main_rows:
        if row["id"] in corrections and row["is_lotte_related"] != corrections[row["id"]]:
            row["is_lotte_related"] = corrections[row["id"]]
            changed += 1

    if not main_rows:
        print("메인 CSV가 비어 있습니다.")
        return

    with LABELED_TITLES_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(main_rows[0].keys()))
        writer.writeheader()
        writer.writerows(main_rows)

    print(f"적용 완료 - {changed}건 수정 ({LABELED_TITLES_CSV})")


def main():
    parser = argparse.ArgumentParser(description="is_lotte_related 재검토")
    parser.add_argument("--all", action="store_true", help="true/false 전체 재평가")
    parser.add_argument("--apply", action="store_true", help="review CSV 수정값을 메인 CSV에 반영")
    args = parser.parse_args()

    if args.apply:
        run_apply()
    else:
        run_review(review_all=args.all)


if __name__ == "__main__":
    main()
