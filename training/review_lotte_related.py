"""
is_lotte_related 필드 재검토 스크립트.

1. [검토] labeled_titles.csv에서 is_lotte_related=true 항목을 GPT로 재평가
         → 원본과 불일치하는 항목을 review_lotte_related.csv로 출력
2. [적용] review_lotte_related.csv에서 corrected_value를 채운 뒤 --apply 실행
         → labeled_titles.csv에 수정값 반영

사용법:
    python training/review_lotte_related.py              # 재평가 (review CSV 생성)
    python training/review_lotte_related.py --all        # true/false 모두 재평가
    python training/review_lotte_related.py --apply      # review CSV → 메인 CSV 반영
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

INPUT_CSV  = Path(__file__).parent / "data" / "labeled_titles.csv"
REVIEW_CSV = Path(__file__).parent / "data" / "review_lotte_related.csv"

REVIEW_HEADERS = [
    "id",
    "title",
    "description_snippet",
    "source_name",
    "published_at",
    "primary_label",
    "original_value",   # 기존 is_lotte_related
    "gpt_value",        # GPT 재평가 결과
    "gpt_reason",       # GPT 판단 근거
    "corrected_value",  # 사람이 최종 수정 (빈칸 = gpt_value 채택)
]

# ── GPT 재평가 프롬프트 ───────────────────────────────────────────────────────

REVIEW_SYSTEM_PROMPT = """당신은 KBO 뉴스 기사와 롯데 자이언츠의 관련성을 판단하는 전문가입니다.

## is_lotte_related 판단 기준
- true : 롯데 자이언츠 소속 선수·구단·경기가 기사의 **주체**인 경우
         롯데 출신 선수의 이적 직후 관련 기사 (맥락상 롯데가 주체)
- false: 롯데가 **상대팀**으로만 언급된 경우
         KBO 전체 순위·기록 기사에서 롯데가 부수적으로 언급된 경우
         트레이드·이적 기사에서 롯데가 거래 당사자가 아닌 경우

## 출력 형식 (JSON만, 설명 없음)
{
  "is_lotte_related": true 또는 false,
  "reason": "판단 근거를 한 문장으로"
}"""


def _call_gpt(title: str, description: str) -> dict:
    user_content = f"제목: {title}"
    if description:
        user_content += f"\ndescription: {description}"

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            "max_tokens": 100,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        },
        timeout=20,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


# ── 재평가 ────────────────────────────────────────────────────────────────────

def run_review(review_all: bool) -> None:
    if not OPENAI_API_KEY:
        print("[ERROR] OPENAI_API_KEY 환경변수가 없습니다.")
        sys.exit(1)

    if not INPUT_CSV.exists():
        print(f"[ERROR] {INPUT_CSV} 파일이 없습니다.")
        sys.exit(1)

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # 재평가 대상 필터
    if review_all:
        candidates = rows
        print(f"전체 재평가 모드 — {len(candidates)}건")
    else:
        candidates = [r for r in rows if r.get("is_lotte_related", "").strip().lower() == "true"]
        print(f"is_lotte_related=true 항목만 재평가 — {len(candidates)}건")

    if not candidates:
        print("재평가 대상이 없습니다.")
        return

    flagged: list[dict] = []
    ok = fail = 0

    for i, row in enumerate(candidates):
        try:
            result = _call_gpt(row["title"], row["description_snippet"])
            gpt_val    = str(result.get("is_lotte_related", True)).lower()
            gpt_reason = result.get("reason", "")
            ok += 1
        except Exception as e:
            gpt_val    = row.get("is_lotte_related", "true").lower()
            gpt_reason = f"GPT 호출 실패: {e}"
            fail += 1

        original = row.get("is_lotte_related", "true").strip().lower()
        is_conflict = gpt_val != original

        if is_conflict:
            flagged.append({
                "id":                  row["id"],
                "title":               row["title"],
                "description_snippet": row["description_snippet"],
                "source_name":         row["source_name"],
                "published_at":        row["published_at"],
                "primary_label":       row["primary_label"],
                "original_value":      original,
                "gpt_value":           gpt_val,
                "gpt_reason":          gpt_reason,
                "corrected_value":     "",  # 사람이 채울 칸
            })

        if (i + 1) % 50 == 0 or (i + 1) == len(candidates):
            pct = (i + 1) / len(candidates) * 100
            print(f"  [{i+1:>4}/{len(candidates)}] {pct:5.1f}%  불일치 {len(flagged)}건  실패 {fail}건",
                  flush=True)

        time.sleep(0.15)

    print(f"\n재평가 완료 — 불일치 {len(flagged)}건 / 전체 {len(candidates)}건")

    if not flagged:
        print("불일치 항목이 없습니다. review CSV를 생성하지 않습니다.")
        return

    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_HEADERS)
        writer.writeheader()
        writer.writerows(flagged)

    print(f"저장 완료 → {REVIEW_CSV}")
    print("\n다음 단계:")
    print("  1. review_lotte_related.csv 열기")
    print("  2. original_value vs gpt_value + gpt_reason 비교")
    print("  3. corrected_value 컬럼에 최종값 입력 (빈칸이면 gpt_value 자동 채택)")
    print("  4. python training/review_lotte_related.py --apply 실행")


# ── 적용 ─────────────────────────────────────────────────────────────────────

def run_apply() -> None:
    if not REVIEW_CSV.exists():
        print(f"[ERROR] {REVIEW_CSV} 파일이 없습니다. 먼저 재평가를 실행하세요.")
        sys.exit(1)

    if not INPUT_CSV.exists():
        print(f"[ERROR] {INPUT_CSV} 파일이 없습니다.")
        sys.exit(1)

    with REVIEW_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        review_rows = list(csv.DictReader(f))

    # id → 최종값 매핑 (corrected_value 우선, 없으면 gpt_value)
    corrections: dict[str, str] = {}
    for r in review_rows:
        final = r["corrected_value"].strip().lower()
        if final not in ("true", "false"):
            final = r["gpt_value"].strip().lower()
        if final in ("true", "false"):
            corrections[r["id"]] = final

    if not corrections:
        print("적용할 수정값이 없습니다.")
        return

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        main_rows = list(csv.DictReader(f))
        fieldnames = main_rows[0].keys() if main_rows else []

    changed = 0
    for row in main_rows:
        if row["id"] in corrections:
            old = row["is_lotte_related"]
            new = corrections[row["id"]]
            if old != new:
                row["is_lotte_related"] = new
                changed += 1

    with INPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(main_rows[0].keys()))
        writer.writeheader()
        writer.writerows(main_rows)

    print(f"적용 완료 — {changed}건 수정됨 → {INPUT_CSV}")


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="is_lotte_related 재검토")
    parser.add_argument("--all",   action="store_true", help="true/false 전체 재평가 (기본: true만)")
    parser.add_argument("--apply", action="store_true", help="review CSV 수정값을 메인 CSV에 반영")
    args = parser.parse_args()

    if args.apply:
        run_apply()
    else:
        run_review(review_all=args.all)


if __name__ == "__main__":
    main()
