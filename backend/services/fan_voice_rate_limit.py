from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import cache

_KST = timezone(timedelta(hours=9))
_WINDOW_SEC = 300
_SLOW_MODE_THRESHOLD = 50
_WRITE_COOLDOWN_SEC = 10
_WRITE_COOLDOWN_SLOW_SEC = 30
_DUPLICATE_WINDOW_SEC = 60


def _now_ts() -> int:
    return int(datetime.now(_KST).timestamp())


def _ttl_seconds() -> int:
    return _WINDOW_SEC + 60


def _read_timestamps(key: str) -> list[int]:
    data = cache.get_json(key)
    if isinstance(data, list):
        return [int(x) for x in data if isinstance(x, int | float)]
    return []


def _write_timestamps(key: str, values: list[int]) -> None:
    cache.set_json(key, values, _ttl_seconds())


def _filter_recent_timestamps(values: list[int], window_sec: int, now_ts: int) -> list[int]:
    return [x for x in values if now_ts - x <= window_sec]


def detect_slow_mode(context_type: str, context_id: str) -> bool:
    now_ts = _now_ts()
    key = f"fanvoice:writes:{context_type}:{context_id}"
    values = _filter_recent_timestamps(_read_timestamps(key), _WINDOW_SEC, now_ts)
    return len(values) >= _SLOW_MODE_THRESHOLD


def record_context_write(context_type: str, context_id: str) -> bool:
    now_ts = _now_ts()
    key = f"fanvoice:writes:{context_type}:{context_id}"
    values = _filter_recent_timestamps(_read_timestamps(key), _WINDOW_SEC, now_ts)
    values.append(now_ts)
    _write_timestamps(key, values)
    return len(values) >= _SLOW_MODE_THRESHOLD


def can_write(session_id: int, *, slow_mode: bool) -> tuple[bool, int]:
    now_ts = _now_ts()
    cooldown = _WRITE_COOLDOWN_SLOW_SEC if slow_mode else _WRITE_COOLDOWN_SEC
    key = f"fanvoice:session:last_write:{session_id}"
    data = cache.get_json(key)
    if isinstance(data, int):
        elapsed = now_ts - data
        if elapsed < cooldown:
            return False, cooldown - elapsed
    return True, 0


def mark_write(session_id: int) -> None:
    key = f"fanvoice:session:last_write:{session_id}"
    cache.set_json(key, _now_ts(), _ttl_seconds())


def is_duplicate_message(session_id: int, message_normalized: str) -> bool:
    now_ts = _now_ts()
    key = f"fanvoice:session:recent_msg:{session_id}"
    data = cache.get_json(key)
    if isinstance(data, dict):
        text = str(data.get("message", ""))
        ts = int(data.get("ts", 0))
        if text == message_normalized and now_ts - ts <= _DUPLICATE_WINDOW_SEC:
            return True
    return False


def mark_message(session_id: int, message_normalized: str) -> None:
    key = f"fanvoice:session:recent_msg:{session_id}"
    cache.set_json(key, {"message": message_normalized, "ts": _now_ts()}, _ttl_seconds())
