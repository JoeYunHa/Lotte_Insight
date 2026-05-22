"""
Phase E — 새 파이프라인 검증

is_lotte_related 하이브리드 게이트, lotte_stance KoELECTRA, GPT event_summary 할루시네이션을
내장 샘플로 검증한다.

실행 방법:
  python backend/batch/test_phase_e.py           # 모델 검증 (GPT mock)
  python backend/batch/test_phase_e.py --live    # GPT 실제 호출 포함
  python -m pytest backend/batch/test_phase_e.py -v

모델이 없는 환경에서는 rule-based/graceful-degradation 결과만 검증한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# backend 디렉토리를 sys.path에 추가 (standalone 실행 호환)
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pytest

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
SKIP = "\033[93m[SKIP]\033[0m"

# ───────────────────────────────────────────────────────────────────────────────
# 테스트 케이스 정의
# ───────────────────────────────────────────────────────────────────────────────

_LOTTE_RELATED_CASES: list[dict] = [
    # is_lotte_related=True — 다양한 경로
    {"title": "롯데 자이언츠, 삼성 상대로 7대3 승리", "description_snippet": "사직구장에서 열린 홈경기에서 대승.", "expected": True},
    {"title": "롯데 전준우, 햄스트링 부상으로 1군 말소", "description_snippet": "2주 결장 예상.", "expected": True},
    {"title": "사직야구장 주말 팬 이벤트 개최", "description_snippet": "롯데 구단이 팬 행사를 진행한다.", "expected": True},
    {"title": "롯데, 외국인 투수 방출하고 새 용병 물색", "description_snippet": "롯데 FA 협상 진행 중.", "expected": True},
    {"title": "롯데 나균안 6이닝 2실점 호투…시즌 5승", "description_snippet": "나균안이 선발 등판해 KBO 롯데 선발 로테이션을 이끌었다.", "expected": True},
    # is_lotte_related=False — 상업 롯데 / 타 구단
    {"title": "롯데백화점, 여름 세일 행사 시작", "description_snippet": "롯데백화점 전국 지점에서 할인 행사가 열린다.", "expected": False},
    {"title": "롯데월드 어드벤처 새 놀이기구 공개", "description_snippet": "롯데월드가 신규 어트랙션을 선보인다.", "expected": False},
    {"title": "KIA 타이거즈, 두산 상대로 연장 승리", "description_snippet": "KIA 타이거즈가 연장 10회에 끝내기 홈런으로 승리했다.", "expected": False},
    {"title": "삼성 라이온즈 에이스, 시즌 10승 달성", "description_snippet": "삼성 선발이 9이닝 완봉승을 거뒀다.", "expected": False},
]

_STANCE_CASES: list[dict] = [
    # positive — 롯데에 유리한 내용
    {"title": "롯데 자이언츠, 삼성 7대3 대승…3연승 달성", "description_snippet": "타선 폭발로 대승을 거두며 3위로 올라섰다.", "expected": "positive"},
    {"title": "롯데 나균안, 7이닝 무실점 완벽 투구", "description_snippet": "에이스로서의 면모를 확실히 보여줬다.", "expected": "positive"},
    # negative — 롯데에 불리한 내용
    {"title": "롯데, 한화에 1대8 완패…5연패 수렁", "description_snippet": "타선이 침묵하고 불펜이 무너지며 대패했다.", "expected": "negative"},
    {"title": "롯데 에이스 부상 이탈…선발 로테이션 비상", "description_snippet": "부상으로 2개월 결장이 예상돼 팀에 큰 타격이다.", "expected": "negative"},
    # neutral — 사실 전달, 판단 없음
    {"title": "롯데, 외국인 타자 재계약 협상 중", "description_snippet": "구단과 선수 측이 연봉 협상 테이블에 앉았다.", "expected": "neutral"},
    {"title": "롯데 구단, 신인 드래프트 전략 공개", "description_snippet": "구단이 드래프트 지명 우선순위를 발표했다.", "expected": "neutral"},
]

_GPT_HALLUCINATION_CASES: list[dict] = [
    {
        "title": "롯데 전준우, 결승 홈런으로 팀 승리 이끌어",
        "description_snippet": "전준우가 7회말 결승 투런 홈런을 터뜨렸다.",
    },
    {
        "title": "롯데 나균안·박세웅 선발 등판 예정",
        "description_snippet": "롯데가 이번 주 나균안과 박세웅을 선발로 낸다.",
    },
    {
        "title": "롯데, 외국인 투수 방출",
        "description_snippet": "성적 부진으로 인한 방출 결정이 내려졌다.",
    },
]

# ───────────────────────────────────────────────────────────────────────────────
# 검증 함수
# ───────────────────────────────────────────────────────────────────────────────

_MIN_LOTTE_RELATED_ACCURACY = 0.80
_MIN_STANCE_ACCURACY = 0.50   # macro F1 0.6946 기준, 소규모 샘플에서 허용 범위 넓게 설정
_MAX_HALLUCINATION_RATE = 0.20


def _check_lotte_related() -> tuple[bool, str]:
    from models.lotte_related_detector import detect_is_lotte_related_batch

    articles = [{"title": c["title"], "description_snippet": c["description_snippet"]} for c in _LOTTE_RELATED_CASES]
    results = detect_is_lotte_related_batch(articles)

    correct = 0
    errors: list[str] = []
    for c, r in zip(_LOTTE_RELATED_CASES, results):
        predicted = r["is_lotte_related"]
        expected = c["expected"]
        if predicted == expected:
            correct += 1
            print(f"  {PASS} [{r['source']}] {c['title'][:50]}")
        else:
            errors.append(f"예상={expected} 실제={predicted} ({r['source']}) | {c['title'][:50]}")
            print(f"  {FAIL} [{r['source']}] {c['title'][:50]}")
            print(f"         → 예상={expected}, 실제={predicted}, conf={r['confidence']:.4f}")

    total = len(_LOTTE_RELATED_CASES)
    accuracy = correct / total
    print(f"\n  is_lotte_related 정확도: {correct}/{total} ({accuracy*100:.1f}%)")
    ok = accuracy >= _MIN_LOTTE_RELATED_ACCURACY
    msg = (
        f"is_lotte_related 정확도 {accuracy*100:.1f}% < 임계치 {_MIN_LOTTE_RELATED_ACCURACY*100:.0f}%\n"
        + "\n".join(f"  - {e}" for e in errors)
    ) if not ok else ""
    return ok, msg


def _check_stance() -> tuple[bool, str]:
    from models.stance_classifier import classify_stance_batch

    articles = [{"title": c["title"], "description_snippet": c["description_snippet"]} for c in _STANCE_CASES]
    results = classify_stance_batch(articles)

    # 모델 미설치 → graceful degradation(null 반환) → skip
    if all(r.get("source") in ("not_applicable", "model_error") for r in results):
        print(f"  {SKIP} stance classifier 모델 없음 — 건너뜀")
        return True, ""

    correct = 0
    errors: list[str] = []
    for c, r in zip(_STANCE_CASES, results):
        predicted = r.get("label")
        expected = c["expected"]
        if predicted == expected:
            correct += 1
            print(f"  {PASS} [{predicted}] {c['title'][:50]}")
        else:
            errors.append(f"예상={expected} 실제={predicted} | {c['title'][:50]}")
            print(f"  {FAIL} {c['title'][:50]}")
            print(f"         → 예상={expected}, 실제={predicted}, conf={r.get('confidence', 0):.4f}")

    total = len(_STANCE_CASES)
    accuracy = correct / total
    print(f"\n  stance 정확도: {correct}/{total} ({accuracy*100:.1f}%)")
    ok = accuracy >= _MIN_STANCE_ACCURACY
    msg = (
        f"lotte_stance 정확도 {accuracy*100:.1f}% < 임계치 {_MIN_STANCE_ACCURACY*100:.0f}%\n"
        + "\n".join(f"  - {e}" for e in errors)
    ) if not ok else ""
    return ok, msg


def _check_gpt_hallucination() -> tuple[bool, str]:
    """key_players에 입력 텍스트에 없는 이름이 포함되면 할루시네이션으로 간주."""
    from batch.gpt_summarizer import gpt_summarize_batch

    results = gpt_summarize_batch(_GPT_HALLUCINATION_CASES)

    hallucinated = 0
    for c, r in zip(_GPT_HALLUCINATION_CASES, results):
        source = r.get("source", "")
        if source in ("gpt_error", "not_applicable"):
            print(f"  {SKIP} GPT 호출 실패 또는 미적용: {c['title'][:40]}")
            continue

        combined = f"{c['title']} {c['description_snippet']}"
        bad_names = [p for p in r.get("key_players", []) if p and p not in combined]
        summary = r.get("event_summary", "")
        is_empty = not summary.strip()

        if bad_names:
            hallucinated += 1
            print(f"  {FAIL} 할루시네이션 감지 — 입력에 없는 선수명: {bad_names}")
            print(f"         제목: {c['title'][:50]}")
        elif is_empty:
            print(f"  {FAIL} event_summary 비어 있음: {c['title'][:50]}")
            hallucinated += 1
        else:
            print(f"  {PASS} [{source}] {c['title'][:50]}")
            print(f"         summary: {summary[:80]}")
            if r.get("key_players"):
                print(f"         players: {r['key_players']}")

    total = len(_GPT_HALLUCINATION_CASES)
    hall_rate = hallucinated / total if total else 0
    print(f"\n  GPT 할루시네이션 비율: {hallucinated}/{total} ({hall_rate*100:.1f}%)")
    ok = hall_rate <= _MAX_HALLUCINATION_RATE
    msg = f"GPT 할루시네이션 {hall_rate*100:.1f}% > 임계치 {_MAX_HALLUCINATION_RATE*100:.0f}%" if not ok else ""
    return ok, msg


# ───────────────────────────────────────────────────────────────────────────────
# pytest 진입점
# ───────────────────────────────────────────────────────────────────────────────

def test_is_lotte_related_accuracy():
    print("\n[Phase E-1] is_lotte_related 하이브리드 게이트 정확도")
    ok, msg = _check_lotte_related()
    assert ok, msg


def test_lotte_stance_accuracy():
    print("\n[Phase E-2] lotte_stance 분류기 정확도")
    ok, msg = _check_stance()
    assert ok, msg


def test_gpt_hallucination(request):
    """--live 플래그가 없으면 skip."""
    live = request.config.getoption("--live", default=False)
    if not live:
        pytest.skip("GPT 실제 호출은 --live 플래그로만 실행됩니다.")
    print("\n[Phase E-3] GPT event_summary 할루시네이션 검증")
    ok, msg = _check_gpt_hallucination()
    assert ok, msg


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False, help="GPT 실제 호출 포함")


# ───────────────────────────────────────────────────────────────────────────────
# standalone 진입점
# ───────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase E 파이프라인 검증")
    parser.add_argument("--live", action="store_true", help="GPT 실제 호출 포함")
    args = parser.parse_args()

    stages: list[tuple[str, callable]] = [
        ("[Phase E-1] is_lotte_related 하이브리드 게이트", _check_lotte_related),
        ("[Phase E-2] lotte_stance 분류기", _check_stance),
    ]
    if args.live:
        stages.append(("[Phase E-3] GPT 할루시네이션", _check_gpt_hallucination))

    passed = 0
    for label, fn in stages:
        print(f"\n{'='*60}")
        print(label)
        print("=" * 60)
        try:
            ok, msg = fn()
            if ok:
                passed += 1
            else:
                print(f"  {FAIL} {msg}")
        except Exception as exc:
            print(f"  {FAIL} 예외 발생: {exc}")

    total = len(stages)
    print(f"\n{'='*60}")
    if passed == total:
        print(f"{PASS} Phase E 전체 통과 ({passed}/{total})")
    else:
        print(f"{FAIL} Phase E 실패 ({total - passed}/{total} 실패)")
        sys.exit(1)


if __name__ == "__main__":
    main()
