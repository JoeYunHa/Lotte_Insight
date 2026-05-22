"""
Unit tests for core/cache.py — ttl_seconds KST correctness.

Key invariant: the "past vs today" boundary must be evaluated in KST,
not server local time (which may be UTC on Railway).
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

_KST = timezone(timedelta(hours=9))


def _kst(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=_KST)


def _ttl(fake_now_kst: datetime, target_date: date) -> int:
    from core.cache import ttl_seconds

    with patch("core.cache.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now_kst
        return ttl_seconds(target_date)


class TestTtlSeconds:
    def test_past_date_returns_86400(self):
        result = _ttl(_kst(2026, 5, 22, 10, 0), date(2026, 5, 21))
        assert result == 86400

    def test_today_returns_seconds_until_midnight(self):
        # KST 10:00 → 14h until midnight = 50400 s
        result = _ttl(_kst(2026, 5, 22, 10, 0), date(2026, 5, 22))
        assert result == 14 * 3600

    def test_today_near_midnight_returns_at_least_60(self):
        # KST 23:59:30 → 30s until midnight, clamped to 60
        result = _ttl(_kst(2026, 5, 22, 23, 59, 30), date(2026, 5, 22))
        assert result == 60

    def test_kst_midnight_boundary_utc_lag(self):
        """
        UTC 15:00 on May 22 == KST 00:00 on May 23.
        A server running UTC would see date.today() = May 22 and treat May 22
        as "today", giving wrong short TTL.  With the KST fix, KST today = May 23
        so May 22 is past → 86400.
        """
        fake_now_kst = _kst(2026, 5, 23, 0, 30, 0)  # just past KST midnight
        result = _ttl(fake_now_kst, date(2026, 5, 22))
        assert result == 86400

    def test_future_date_treated_as_today_ttl(self):
        # Requesting TTL for a future date: should not return 86400 (past logic),
        # but the seconds-to-midnight of *today* logic will still fire.
        # The actual value will be > 86400; we just check it's not 86400.
        result = _ttl(_kst(2026, 5, 22, 10, 0), date(2026, 5, 23))
        assert result != 86400
        assert result >= 60
