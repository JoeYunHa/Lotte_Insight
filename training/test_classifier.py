"""Quick inference test for the trained KoELECTRA classifier.

Usage:
    python test_classifier.py                          # 내장 샘플 실행
    python test_classifier.py --title "기사 제목" --desc "설명" --expected MATCH_RELATED
    python test_classifier.py --model-dir path/to/model
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from models.classifier import classify

SAMPLE_ARTICLES = [
    {
        "title": "롯데 나균안, 시즌 5승 달성…선발 로테이션 안정화",
        "description_snippet": "나균안이 두산전 6이닝 2실점 호투로 시즌 5승을 따냈다.",
        "expected": "MATCH_RELATED",
    },
    {
        "title": "롯데 전준우, 햄스트링 부상으로 1군 엔트리 말소",
        "description_snippet": "전준우가 어제 경기 도중 햄스트링 부상을 당해 말소됐다. 복귀는 2주 뒤.",
        "expected": "INJURY_ROSTER",
    },
    {
        "title": "롯데, 외국인 투수 방출…새 용병 물색 중",
        "description_snippet": "롯데가 부진한 외국인 투수를 방출하고 대체 자원을 물색 중이다.",
        "expected": "TRANSACTION_CONTRACT",
    },
    {
        "title": "롯데 타자진 타율 .285 기록…리그 2위 수준",
        "description_snippet": "롯데 타선이 OPS .800을 넘기며 리그 상위권 성적을 유지하고 있다.",
        "expected": "PERFORMANCE_ANALYSIS",
    },
    {
        "title": "롯데 염경엽 감독 '선발진 안정이 우선'",
        "description_snippet": "염경엽 감독이 경기 후 기자회견에서 선발진 운용 방향을 밝혔다.",
        "expected": "INTERVIEW",
    },
    {
        "title": "롯데, 사직구장 팬 이벤트 행사 개최",
        "description_snippet": "롯데 구단이 이번 주말 홈경기에서 팬 참여 이벤트를 진행한다고 발표했다.",
        "expected": "CLUB_OPERATION",
    },
]


def run(articles: list[dict], model_dir: str | None = None) -> None:
    if model_dir:
        import os
        os.environ["CLASSIFIER_MODEL_DIR"] = model_dir
        import models.classifier as _clf
        _clf._model_loaded = False

    correct = 0
    print("=" * 60)
    for i, article in enumerate(articles, 1):
        result = classify(article["title"], article.get("description_snippet", ""))
        predicted = result["label"]
        expected = article.get("expected", "")
        mark = "O" if predicted == expected else "X"
        if predicted == expected:
            correct += 1

        print(f"[{i}] {mark}  제목: {article['title']}")
        print(f"      예상: {expected or '-':25s}  예측: {predicted}  (conf={result['confidence']:.4f})")
        if result["secondary_labels"]:
            print(f"      보조: {', '.join(result['secondary_labels'])}")
        print()

    total = len(articles)
    print(f"정확도: {correct}/{total} ({correct/total*100:.1f}%)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="KoELECTRA 분류 모델 테스트")
    parser.add_argument("--title", type=str, default=None, help="기사 제목")
    parser.add_argument("--desc", type=str, default="", help="기사 설명 (선택)")
    parser.add_argument("--expected", type=str, default="", help="예상 라벨 (선택)")
    parser.add_argument("--model-dir", type=str, default=None, help="모델 디렉토리 경로")
    args = parser.parse_args()

    if args.title:
        articles = [{"title": args.title, "description_snippet": args.desc, "expected": args.expected}]
    else:
        print("=== 내장 샘플 6건으로 테스트 ===\n")
        articles = SAMPLE_ARTICLES

    run(articles, model_dir=args.model_dir)


if __name__ == "__main__":
    main()
