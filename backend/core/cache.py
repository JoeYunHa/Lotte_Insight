"""
Redis 캐시 유틸리티.

Redis가 없거나 연결 실패 시 캐시 없이 정상 동작한다 (graceful degradation).
"""

import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any

from core.time_utils import KST

logger = logging.getLogger(__name__)

_client = None
_last_check_time: float = 0.0
_CHECK_INTERVAL = 60.0  # seconds between reconnect attempts when Redis is down
_url_missing_logged = False
_client_lock = threading.Lock()


def _get_client():
    """
    Get or (re)connect the Redis client (thread-safe).

    A failed ping does NOT permanently disable the cache — we retry every
    `_CHECK_INTERVAL` seconds so the application recovers automatically once
    Redis is back online. Double-checked locking prevents redundant reconnects
    under concurrent access.
    """
    global _client, _last_check_time, _url_missing_logged

    if _client is not None:
        return _client

    with _client_lock:
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
    now_kst = datetime.now(KST)
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
    except Exception as exc:
        logger.warning("Redis GET 실패 key=%s: %s", key, exc)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Corrupted cache entry — discard and let the caller re-populate.
        logger.exception("Redis 캐시 데이터 손상 (key=%s); 항목 삭제 후 재생성 필요", key)
        return None


def set_json(key: str, value: Any, ttl: int) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        serialized = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        # Serialization failure is a programming error, not an infra issue.
        logger.exception("캐시 직렬화 실패 (key=%s) — 캐시에 저장하지 않음", key)
        return
    try:
        client.setex(key, ttl, serialized)
    except Exception as exc:
        logger.warning("Redis SETEX 실패 key=%s: %s", key, exc)


def delete(key: str) -> None:
    """Delete a cache key (no-op if Redis is unavailable)."""
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception as exc:
        logger.warning("Redis DEL 실패 key=%s: %s", key, exc)


def incr(key: str, ttl: int) -> int:
    """Atomically increment a counter and set TTL on first write.

    Returns the new counter value, or 0 if Redis is unavailable.
    Uses a fixed window: TTL is set only when the key is first created
    (count == 1), so the window resets naturally when the key expires.
    """
    client = _get_client()
    if client is None:
        return 0
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, ttl)
        return count
    except Exception as exc:
        logger.warning("Redis INCR 실패 key=%s: %s", key, exc)
        return 0


def get_counter(key: str) -> int:
    """Return current counter value, or 0 if key absent or Redis unavailable."""
    client = _get_client()
    if client is None:
        return 0
    try:
        raw = client.get(key)
        return int(raw) if raw else 0
    except Exception as exc:
        logger.warning("Redis GET counter 실패 key=%s: %s", key, exc)
        return 0
