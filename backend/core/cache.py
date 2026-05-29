"""
Redis 캐시 유틸리티.

Redis가 없거나 연결 실패 시 캐시 없이 정상 동작한다 (graceful degradation).
"""

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_last_check_time: float = 0.0
_CHECK_INTERVAL = 60.0  # seconds between reconnect attempts when Redis is down
_url_missing_logged = False


def _get_client():
    """
    Get or (re)connect the Redis client.

    Unlike the previous implementation, a failed ping does NOT permanently
    disable the cache — we retry every `_CHECK_INTERVAL` seconds so the
    application recovers automatically once Redis is back online.
    """
    global _client, _last_check_time, _url_missing_logged

    if _client is not None:
        return _client

    now = time.time()
    if now - _last_check_time < _CHECK_INTERVAL:
        return None
    _last_check_time = now

    from core.config import settings
    url = getattr(settings, "redis_url", "")
    if not url:
        if not _url_missing_logged:
            logger.info("REDIS_URL 미설정 — 캐시 비활성화")
            _url_missing_logged = True
        return None

    try:
        import redis as _redis
        c = _redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        c.ping()
        _client = c
        logger.info("Redis 연결 완료: %s", url.split("@")[-1])
    except Exception as exc:
        logger.warning(
            "Redis 연결 실패 (%s) — 캐시 없이 동작 (다음 재시도 %.0fs)",
            exc,
            _CHECK_INTERVAL,
        )

    return _client


def ttl_seconds(target_date: date) -> int:
    """과거 날짜: 24시간 고정. 오늘: KST 자정까지 남은 초."""
    _KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(_KST)
    if target_date < now_kst.date():
        return 86400
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
