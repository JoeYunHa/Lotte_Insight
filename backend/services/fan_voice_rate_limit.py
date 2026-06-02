from __future__ import annotations

from datetime import datetime

from core import cache
from core.time_utils import KST
from services.cache_keys import CacheKeyBuilder

_WINDOW_SEC = 300
_SLOW_MODE_THRESHOLD = 50
_WRITE_COOLDOWN_SEC = 10
_WRITE_COOLDOWN_SLOW_SEC = 30
_DUPLICATE_WINDOW_SEC = 60


def _now_ts() -> int:
    return int(datetime.now(KST).timestamp())


def _ttl_seconds() -> int:
    return _WINDOW_SEC + 60



def detect_slow_mode(context_type: str, context_id: str) -> bool:
    key = CacheKeyBuilder.rate_limit_context_writes(context_type, context_id)
    return cache.get_counter(key) >= _SLOW_MODE_THRESHOLD


def record_context_write(context_type: str, context_id: str) -> bool:
    key = CacheKeyBuilder.rate_limit_context_writes(context_type, context_id)
    count = cache.incr(key, _WINDOW_SEC + 60)
    return count >= _SLOW_MODE_THRESHOLD


def can_write(session_id: int, *, slow_mode: bool) -> tuple[bool, int]:
    now_ts = _now_ts()
    cooldown = _WRITE_COOLDOWN_SLOW_SEC if slow_mode else _WRITE_COOLDOWN_SEC
    key = CacheKeyBuilder.rate_limit_session_last_write(session_id)
    data = cache.get_json(key)
    if isinstance(data, int):
        elapsed = now_ts - data
        if elapsed < cooldown:
            return False, cooldown - elapsed
    return True, 0


def mark_write(session_id: int) -> None:
    key = CacheKeyBuilder.rate_limit_session_last_write(session_id)
    cache.set_json(key, _now_ts(), _ttl_seconds())


_RECENT_MESSAGE_RING_SIZE = 5


def _read_recent_messages(session_id: int) -> list[dict]:
    """Read the recent-messages ring buffer (back-compat with legacy dict)."""
    key = CacheKeyBuilder.rate_limit_session_recent_msg(session_id)
    data = cache.get_json(key)
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    if isinstance(data, dict):
        # Legacy single-entry format
        return [data]
    return []


def is_duplicate_message(session_id: int, message_normalized: str) -> bool:
    """Check the last N messages (ring buffer) to block A/B/A/B ping-pong."""
    now_ts = _now_ts()
    for entry in _read_recent_messages(session_id):
        text = str(entry.get("message", ""))
        ts = int(entry.get("ts", 0))
        if text == message_normalized and now_ts - ts <= _DUPLICATE_WINDOW_SEC:
            return True
    return False


def mark_message(session_id: int, message_normalized: str) -> None:
    key = CacheKeyBuilder.rate_limit_session_recent_msg(session_id)
    ring = _read_recent_messages(session_id)
    ring.append({"message": message_normalized, "ts": _now_ts()})
    # Trim to the most recent N entries (ring buffer)
    if len(ring) > _RECENT_MESSAGE_RING_SIZE:
        ring = ring[-_RECENT_MESSAGE_RING_SIZE:]
    cache.set_json(key, ring, _ttl_seconds())
