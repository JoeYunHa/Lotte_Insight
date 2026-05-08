"""Quick inference test for the trained KoBART summarizer.

Usage:
    python test_summarizer.py                      # 내장 샘플 실행
    python test_summarizer.py --title "기사 제목" --desc "설명" --label MATCH_RELATED
    python test_summarizer.py --beams 4 --max-len 192
"""

from __future__ import annotations

import argparse
import json
import re

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList

from collect_utils import clean_snippet
from settings import (
    ARTICLE_SNIPPET_LENGTH,
    DEFAULT_SUMMARIZER_EARLY_STOPPING,
    DEFAULT_SUMMARIZER_LENGTH_PENALTY,
    DEFAULT_SUMMARIZER_MAX_SOURCE_LEN,
    DEFAULT_SUMMARIZER_MAX_TARGET_LEN,
    DEFAULT_SUMMARIZER_NO_REPEAT_NGRAM,
    DEFAULT_SUMMARIZER_NUM_BEAMS,
    SUMMARIZER_MODEL_DIR,
)

SAMPLE_ARTICLES = [
    {
        "title": "롯데 나균안, 시즌 5승 달성…선발 로테이션 안정화",
        "description_snippet": "나균안이 두산전 6이닝 2실점 호투로 시즌 5승을 따냈다. 롯데 선발진이 흔들리는 가운데 에이스 역할을 톡톡히 해내고 있다.",
        "published_at": "2026-05-06",
        "primary_label": "MATCH_RELATED",
        "game_context": "",
    },
    {
        "title": "롯데 외야수 전준우 햄스트링 부상…2주 결장 예상",
        "description_snippet": "전준우가 어제 경기 도중 햄스트링 부상을 당해 1군 엔트리에서 말소됐다. 복귀 시점은 2주 뒤로 예상된다.",
        "published_at": "2026-05-05",
        "primary_label": "INJURY_ROSTER",
        "game_context": "",
    },
    {
        "title": "롯데, KIA에 3연전 2승 1패…3위 등극",
        "description_snippet": "롯데가 KIA를 상대로 3연전 2승을 거두며 리그 3위로 올라섰다. 타선이 3경기 합계 22득점을 올리며 폭발했다.",
        "published_at": "2026-05-04",
        "primary_label": "MATCH_RELATED",
        "game_context": "vs KIA 3연전",
    },
    {
        "title": "롯데 구단, 외국인 투수 교체 결정…새 용병 물색 중",
        "description_snippet": "롯데가 부진한 외국인 투수를 방출하고 새 용병을 물색 중이다. 대체 자원은 이번 주 내 결정될 예정이다.",
        "published_at": "2026-05-03",
        "primary_label": "TRANSACTION_CONTRACT",
        "game_context": "",
    },
]


class JsonClosedStopping(StoppingCriteria):
    """JSON 객체가 완전히 닫히면(중괄호 균형) 생성을 중단한다."""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self._depth = 0
        self._started = False

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        text = self.tokenizer.decode(input_ids[0], skip_special_tokens=True)
        depth = 0
        started = False
        for ch in text:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
        return started and depth <= 0


def _extract_first_json(text: str) -> dict | None:
    """문자열에서 첫 번째 균형 잡힌 JSON 객체를 추출한다."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # 손상된 JSON — 핵심 필드만 regex로 추출
                    return _regex_extract(candidate)
    return None


def _regex_extract(text: str) -> dict:
    """JSON 파싱 실패 시 event_summary 등 핵심 필드를 정규식으로 추출한다."""
    result: dict = {}
    m = re.search(r'"event_summary"\s*:\s*"([^"]+)"', text)
    if m:
        result["event_summary"] = m.group(1)
    m = re.search(r'"lotte_stance"\s*:\s*"([^"]+)"', text)
    if m:
        result["lotte_stance"] = m.group(1)
    players: list[str] = re.findall(r'"key_players"\s*:\s*\[([^\]]*)\]', text)
    if players:
        names = re.findall(r'"([^"]+)"', players[0])
        result["key_players"] = [n for n in names if n != "nan"]
    return result


def build_source_text(row: dict) -> str:
    parts = ["뉴스 요약:"]
    parts.append(f"title: {clean_snippet(str(row.get('title', '')).strip())}")
    description = clean_snippet(str(row.get("description_snippet", "") or "").strip())
    if description:
        parts.append(f"description: {description[:ARTICLE_SNIPPET_LENGTH]}")
    published_at = str(row.get("published_at", "") or "").strip()
    if published_at:
        parts.append(f"published_at: {published_at}")
    topic_label = str(row.get("primary_label", "") or "").strip()
    if topic_label:
        parts.append(f"topic_label: {topic_label}")
    game_context = str(row.get("game_context", "") or "").strip()
    if game_context:
        parts.append(f"game_context: {game_context}")
    return "\n".join(parts)


def summarize(
    articles: list[dict],
    model_dir: str | None = None,
    max_source_len: int = DEFAULT_SUMMARIZER_MAX_SOURCE_LEN,
    max_target_len: int = DEFAULT_SUMMARIZER_MAX_TARGET_LEN,
    num_beams: int = DEFAULT_SUMMARIZER_NUM_BEAMS,
    length_penalty: float = DEFAULT_SUMMARIZER_LENGTH_PENALTY,
    no_repeat_ngram_size: int = DEFAULT_SUMMARIZER_NO_REPEAT_NGRAM,
) -> list[dict]:
    model_path = model_dir or str(SUMMARIZER_MODEL_DIR)
    print(f"모델 로드 중: {model_path}")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
    model.eval()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    print(f"디바이스: {device}\n")

    results = []
    for article in articles:
        source = build_source_text(article)
        inputs = tokenizer(
            source,
            max_length=max_source_len,
            truncation=True,
            return_tensors="pt",
        ).to(device)

        stopping = StoppingCriteriaList([JsonClosedStopping(tokenizer)])

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_target_len,
                num_beams=num_beams,
                length_penalty=length_penalty,
                no_repeat_ngram_size=no_repeat_ngram_size,
                early_stopping=DEFAULT_SUMMARIZER_EARLY_STOPPING,
                stopping_criteria=stopping,
            )

        raw = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        parsed = _extract_first_json(raw)
        results.append({"raw": raw, "parsed": parsed})

    return results


def main():
    parser = argparse.ArgumentParser(description="KoBART 요약 모델 테스트")
    parser.add_argument("--title", type=str, default=None, help="기사 제목")
    parser.add_argument("--desc", type=str, default="", help="기사 설명 (선택)")
    parser.add_argument("--label", type=str, default="", help="라벨 (예: MATCH_RELATED)")
    parser.add_argument("--date", type=str, default="", help="발행일 (예: 2026-05-06)")
    parser.add_argument("--game-context", type=str, default="", help="경기 컨텍스트 (선택)")
    parser.add_argument("--model-dir", type=str, default=None, help="모델 디렉토리 경로")
    parser.add_argument("--beams", type=int, default=DEFAULT_SUMMARIZER_NUM_BEAMS, help="빔 수")
    parser.add_argument("--max-len", type=int, default=DEFAULT_SUMMARIZER_MAX_TARGET_LEN, help="최대 출력 토큰 수")
    parser.add_argument("--length-penalty", type=float, default=DEFAULT_SUMMARIZER_LENGTH_PENALTY, help="길이 패널티")
    parser.add_argument("--no-repeat-ngram", type=int, default=DEFAULT_SUMMARIZER_NO_REPEAT_NGRAM, help="반복 억제 n-gram 크기")
    parser.add_argument("--raw", action="store_true", help="파싱 없이 원본 출력 표시")
    args = parser.parse_args()

    if args.title:
        articles = [
            {
                "title": args.title,
                "description_snippet": args.desc,
                "published_at": args.date,
                "primary_label": args.label,
                "game_context": args.game_context,
            }
        ]
    else:
        print("=== 내장 샘플 4건으로 테스트 ===\n")
        articles = SAMPLE_ARTICLES

    results = summarize(
        articles,
        model_dir=args.model_dir,
        num_beams=args.beams,
        max_target_len=args.max_len,
        length_penalty=args.length_penalty,
        no_repeat_ngram_size=args.no_repeat_ngram,
    )

    print("=" * 60)
    for i, (article, result) in enumerate(zip(articles, results), 1):
        parsed = result["parsed"]
        parse_ok = parsed is not None

        event_summary = parsed.get("event_summary", "") if parse_ok else ""
        key_players = [p for p in (parsed.get("key_players") or []) if p and p != "nan"] if parse_ok else []
        lotte_stance = parsed.get("lotte_stance", "") if parse_ok else ""

        status = "JSON OK" if parse_ok else "JSON 파싱 실패"
        print(f"[{i}] 제목:    {article['title']}")
        print(f"     라벨:    {article.get('primary_label', '-')}  [{status}]")

        if event_summary:
            print(f"     요약:    {event_summary}")
        else:
            print(f"     요약:    (추출 실패)")

        if key_players:
            print(f"     주요선수: {', '.join(key_players)}")
        if lotte_stance:
            print(f"     분위기:  {lotte_stance}")

        if args.raw or not parse_ok:
            print(f"     [RAW] {result['raw'][:300]}")
        print()


if __name__ == "__main__":
    main()
