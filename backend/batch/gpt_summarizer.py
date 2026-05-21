"""
GPT-4o mini event_summary + key_players generator.

Called only for is_lotte_related=True articles where:
  primary_label in settings.gpt_summary_labels (MATCH_RELATED, INJURY_ROSTER, TRANSACTION_CONTRACT)

Returns per-article: {"event_summary": str, "key_players": list[str], "source": str}
"""

import functools
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import openai

from core.config import settings

logger = logging.getLogger(__name__)

_EMPTY = {"event_summary": "", "key_players": [], "source": "not_applicable"}
_ERROR = {"event_summary": "", "key_players": [], "source": "gpt_error"}

_SYSTEM_PROMPT = (
    "당신은 KBO 롯데 자이언츠 야구 기사 분석가입니다.\n"
    "아래 기사 제목과 설명을 읽고 JSON만 출력하세요. 다른 텍스트는 출력하지 마세요.\n\n"
    "출력 형식:\n"
    '{"event_summary": "핵심 사건 1~2문장 요약", "key_players": ["선수명1", "선수명2"]}\n\n'
    "규칙:\n"
    "- event_summary: 제목/설명에 있는 사실만 요약. 없는 내용 생성 금지.\n"
    "- key_players: 제목/설명에 명시된 선수명만 포함. 추측 금지.\n"
    "- 선수명이 없으면 key_players는 빈 배열 [].\n"
    "- 반드시 유효한 JSON 한 줄만 출력."
)

_MAX_WORKERS = 4
_TITLE_MAX = 80
_SNIPPET_MAX = 200


@functools.lru_cache(maxsize=1)
def _get_client() -> openai.OpenAI:
    return openai.OpenAI(api_key=settings.openai_api_key)


def _build_user_message(title: str, description_snippet: str) -> str:
    t = title[:_TITLE_MAX].strip()
    s = (description_snippet or "")[:_SNIPPET_MAX].strip()
    if s:
        return f"제목: {t}\n설명: {s}"
    return f"제목: {t}"


def _parse_response(text: str) -> dict:
    text = text.strip()
    try:
        data = json.loads(text)
        return {
            "event_summary": str(data.get("event_summary") or ""),
            "key_players": [str(p) for p in (data.get("key_players") or []) if p],
            "source": "gpt",
        }
    except json.JSONDecodeError:
        pass

    # Regex fallback
    summary_match = re.search(r'"event_summary"\s*:\s*"([^"]*)"', text)
    players_match = re.search(r'"key_players"\s*:\s*\[([^\]]*)\]', text)
    summary = summary_match.group(1) if summary_match else ""
    players: list[str] = []
    if players_match:
        raw = players_match.group(1)
        players = [p.strip().strip('"') for p in raw.split(",") if p.strip().strip('"')]
    if summary:
        return {"event_summary": summary, "key_players": players, "source": "gpt_regex_fallback"}

    logger.warning("GPT response parse failed: %s", text[:120])
    return dict(_ERROR)


def _call_gpt(title: str, description_snippet: str) -> dict:
    try:
        response = _get_client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(title, description_snippet)},
            ],
            max_tokens=200,
            temperature=0.0,
        )
        text = response.choices[0].message.content or ""
        return _parse_response(text)
    except Exception as exc:
        logger.error("GPT summarization failed for '%s': %s", title[:40], exc)
        return dict(_ERROR)


def gpt_summarize_batch(
    articles: list[dict],
) -> list[dict]:
    """
    articles: list of {"title": str, "description_snippet": str}
    Returns list of {"event_summary": str, "key_players": list[str], "source": str}
    in the same order.
    """
    if not articles:
        return []

    results: list[dict] = [None] * len(articles)  # type: ignore[list-item]

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                _call_gpt,
                a["title"],
                a.get("description_snippet", ""),
            ): i
            for i, a in enumerate(articles)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                logger.error("Unexpected error in gpt_summarize_batch[%d]: %s", idx, exc)
                results[idx] = dict(_ERROR)

    return results
