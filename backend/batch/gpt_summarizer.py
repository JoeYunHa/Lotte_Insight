"""
GPT-4o mini event_summary + key_players generator.
"""

import functools
import json
import logging
import re
import threading
import time

import openai

from batch.parallel_utils import run_indexed_parallel
from core import cache
from core.config import settings
from services.cache_keys import CacheKeyBuilder

logger = logging.getLogger(__name__)

_ERROR = {"event_summary": "", "key_players": [], "source": "gpt_error"}

_SYSTEM_PROMPT = (
    "당신은 KBO 롯데 자이언츠 야구 기사 분석가입니다.\n"
    "아래 기사 제목과 설명을 보고 JSON만 출력하세요. 다른 텍스트는 출력하지 마세요.\n\n"
    "출력 형식:\n"
    '{"event_summary": "핵심 사건 1~2문장 요약", "key_players": ["선수명", "선수명"]}\n\n'
    "규칙:\n"
    "- event_summary: 제목/설명에 있는 사실만 요약. 없는 내용 생성 금지.\n"
    "- key_players: 제목/설명에 명시된 선수명만 포함. 추론 금지.\n"
    "- 선수명이 없으면 key_players는 빈 배열 [].\n"
    "- 반드시 유효한 JSON 객체만 출력."
)

# Sequential execution to stay within RPM limits; inter-request delay gives ~120 req/min max.
_MAX_WORKERS = 1
_INTER_REQUEST_DELAY = 0.5
_TITLE_MAX = 80
_SNIPPET_MAX = 200
_GPT_SUMMARY_TTL = 7 * 86400  # 7 days — article content is immutable after collection


class _DailyLimitExceeded(Exception):
    """Raised when OpenAI RPD (requests per day) limit is exhausted."""


@functools.lru_cache(maxsize=1)
def _get_client() -> openai.OpenAI:
    # max_retries=0: SDK auto-retry disabled. RPD exhaustion makes retries futile;
    # RPM throttling is handled by _INTER_REQUEST_DELAY + caller-level abort.
    return openai.OpenAI(api_key=settings.openai_api_key, max_retries=0)


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
    cache_key = CacheKeyBuilder.gpt_summary(title=title, snippet=description_snippet)
    cached = cache.get_json(cache_key)
    if cached is not None:
        logger.debug("GPT summary cache hit for '%s'", title[:40])
        return cached

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
        result = _parse_response(text)
        if result.get("source") != "gpt_error":
            cache.set_json(cache_key, result, _GPT_SUMMARY_TTL)
        return result
    except openai.RateLimitError as exc:
        # RPD (daily) exhaustion: retrying within the same day is futile — abort the batch.
        if "requests per day" in str(exc) or "RPD" in str(exc):
            logger.error("OpenAI daily request limit (RPD) exhausted, aborting batch: %s", exc)
            raise _DailyLimitExceeded() from exc
        logger.error("GPT summarization failed for '%s': %s", title[:40], exc)
        return dict(_ERROR)
    except (
        openai.APIError,
        openai.APIConnectionError,
        TimeoutError,
        ValueError,
        IndexError,
        KeyError,
    ) as exc:
        logger.error("GPT summarization failed for '%s': %s", title[:40], exc)
        return dict(_ERROR)


def gpt_summarize_batch(articles: list[dict]) -> list[dict]:
    if not articles:
        return []

    daily_limit_hit = threading.Event()

    def _worker(article: dict) -> dict:
        if daily_limit_hit.is_set():
            return dict(_ERROR)
        time.sleep(_INTER_REQUEST_DELAY)
        return _call_gpt(article["title"], article.get("description_snippet", ""))

    def _on_error(idx: int, exc: Exception) -> dict:
        if isinstance(exc, _DailyLimitExceeded):
            daily_limit_hit.set()
            logger.warning("Skipping remaining articles: OpenAI RPD limit exhausted")
        else:
            logger.error("Unexpected error in gpt_summarize_batch[%d]: %s", idx, exc)
        return dict(_ERROR)

    return run_indexed_parallel(
        articles,
        _worker,
        max_workers=_MAX_WORKERS,
        on_error=_on_error,
    )
