"""
GPT-4o mini event_summary + key_players generator.
"""

import functools
import json
import logging
import re
import threading
import time
from collections.abc import Callable

import openai

from batch.parallel_utils import run_indexed_parallel
from core import cache
from core.config import settings
from services.cache_keys import CacheKeyBuilder

logger = logging.getLogger(__name__)

_ERROR = {"event_summary": "", "key_players": [], "source": "gpt_error"}
_LABEL_ERROR = {"label": "ETC", "confidence": 0.0, "secondary_labels": [], "source": "gpt_error"}

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
# GPT receives up to 300 chars; model gates (KoELECTRA) use the shorter
# article_description_snippet_length (default 120) set during item normalization.
_SNIPPET_MAX = 300
_GPT_SUMMARY_TTL = 7 * 86400  # 7 days — article content is immutable after collection
_GPT_LABEL_TTL = 7 * 86400

_VALID_LABELS = {
    "INJURY_ROSTER",
    "TRANSACTION_CONTRACT",
    "MATCH_RELATED",
    "PERFORMANCE_ANALYSIS",
    "INTERVIEW",
    "CLUB_OPERATION",
    "ETC",
}

_LABEL_SYSTEM_PROMPT = (
    "You classify Korean KBO Lotte Giants news articles. Return only a valid JSON object.\n\n"
    "Labels:\n"
    "- MATCH_RELATED: game result, lineup, game preview/review, in-game performance.\n"
    "- INJURY_ROSTER: injury, rehab, roster registration/call-up/send-down.\n"
    "- TRANSACTION_CONTRACT: trade, signing, release, FA, contract, foreign-player move.\n"
    "- PERFORMANCE_ANALYSIS: statistics, form, tactical or performance analysis.\n"
    "- INTERVIEW: player/coach/front-office quote or interview focused article.\n"
    "- CLUB_OPERATION: club business, front office, stadium, event, fan operation.\n"
    "- ETC: related but none of the above.\n\n"
    "Use the title and snippet only. Do not infer facts not present in the input.\n"
    "Output schema: {\"label\":\"MATCH_RELATED\", \"confidence\":0.0, \"secondary_labels\":[]}"
)


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


def _build_label_user_message(title: str, description_snippet: str) -> str:
    t = title[:_TITLE_MAX].strip()
    s = (description_snippet or "")[:_SNIPPET_MAX].strip()
    if s:
        return f"title: {t}\nsnippet: {s}"
    return f"title: {t}"


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


def _parse_label_response(text: str) -> dict:
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        logger.warning("GPT label response parse failed: %s", text[:120])
        return dict(_LABEL_ERROR)

    label = str(data.get("label") or "ETC").strip().upper()
    if label not in _VALID_LABELS:
        label = "ETC"

    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    secondary_labels: list[str] = []
    for raw_label in data.get("secondary_labels") or []:
        secondary = str(raw_label).strip().upper()
        if secondary in _VALID_LABELS and secondary != label and secondary not in secondary_labels:
            secondary_labels.append(secondary)

    return {
        "label": label,
        "confidence": round(confidence, 4),
        "secondary_labels": secondary_labels,
        "source": "gpt",
    }


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


def _call_gpt_label(title: str, description_snippet: str) -> dict:
    cache_key = CacheKeyBuilder.gpt_label(title=title, snippet=description_snippet)
    cached = cache.get_json(cache_key)
    if cached is not None:
        logger.debug("GPT label cache hit for '%s'", title[:40])
        return cached

    try:
        response = _get_client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _LABEL_SYSTEM_PROMPT},
                {"role": "user", "content": _build_label_user_message(title, description_snippet)},
            ],
            max_tokens=120,
            temperature=0.0,
        )
        text = response.choices[0].message.content or ""
        result = _parse_label_response(text)
        if result.get("source") != "gpt_error":
            cache.set_json(cache_key, result, _GPT_LABEL_TTL)
        return result
    except openai.RateLimitError as exc:
        if "requests per day" in str(exc) or "RPD" in str(exc):
            logger.error("OpenAI daily request limit (RPD) exhausted, aborting label batch: %s", exc)
            raise _DailyLimitExceeded() from exc
        logger.error("GPT label classification failed for '%s': %s", title[:40], exc)
        return dict(_LABEL_ERROR)
    except (
        openai.APIError,
        openai.APIConnectionError,
        TimeoutError,
        ValueError,
        IndexError,
        KeyError,
    ) as exc:
        logger.error("GPT label classification failed for '%s': %s", title[:40], exc)
        return dict(_LABEL_ERROR)


def _run_gpt_batch(
    articles: list[dict],
    call_fn: "Callable[[str, str], dict]",
    error_payload: dict,
    batch_name: str,
) -> list[dict]:
    if not articles:
        return []

    daily_limit_hit = threading.Event()

    def _worker(article: dict) -> dict:
        if daily_limit_hit.is_set():
            return dict(error_payload)
        time.sleep(_INTER_REQUEST_DELAY)
        return call_fn(article["title"], article.get("description_snippet", ""))

    def _on_error(idx: int, exc: Exception) -> dict:
        if isinstance(exc, _DailyLimitExceeded):
            daily_limit_hit.set()
            logger.warning("Skipping remaining %s requests: OpenAI RPD limit exhausted", batch_name)
        else:
            logger.error("Unexpected error in %s[%d]: %s", batch_name, idx, exc)
        return dict(error_payload)

    return run_indexed_parallel(articles, _worker, max_workers=_MAX_WORKERS, on_error=_on_error)


def gpt_summarize_batch(articles: list[dict]) -> list[dict]:
    return _run_gpt_batch(articles, _call_gpt, _ERROR, "gpt_summarize_batch")


def gpt_classify_labels_batch(articles: list[dict]) -> list[dict]:
    return _run_gpt_batch(articles, _call_gpt_label, _LABEL_ERROR, "gpt_classify_labels_batch")
