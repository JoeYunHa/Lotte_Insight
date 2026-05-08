"""
Redis 캐시 유틸리티.

Redis가 없거나 연결 실패 시 캐시 없이 정상 동작한다 (graceful degradation).
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_client_checked = False


def _get_client():
    global _client, _client_checked
    if _client_checked:
        return _client

    _client_checked = True

    from core.config import settings
    url = getattr(settings, "redis_url", "")
    if not url:
        logger.info("REDIS_URL 미설정 — 캐시 비활성화")
        return None

    try:
        import redis as _redis
        c = _redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        c.ping()
        _client = c
        logger.info("Redis 연결 완료: %s", url.split("@")[-1])
    except Exception as exc:
        logger.warning("Redis 연결 실패 (%s) — 캐시 없이 동작", exc)

    return _client


def ttl_seconds(target_date: date) -> int:
    """과거 날짜: 24시간 고정. 오늘: KST 자정까지 남은 초."""
    if target_date < date.today():
        return 86400
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    midnight_kst = (now_kst + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(int((midnight_kst - now_kst).total_seconds()), 60)


def get_json(key: str) -> Any | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Redis GET 실패 key=%s: %s", key, exc)
        return None


def set_json(key: str, value: Any, ttl: int) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception as exc:
        logger.warning("Redis SETEX 실패 key=%s: %s", key, exc)
