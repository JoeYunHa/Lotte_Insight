"""Tests for centralized cache key builder."""

from datetime import date

from services.cache_keys import CacheKeyBuilder, fanvoice_review_key, player_report_key, team_report_key


def test_fan_voice_review_key_format():
    """Fan voice review cache key should follow consistent format."""
    key = CacheKeyBuilder.fan_voice_review(
        context_type="home",
        context_id="today",
        game_date=date(2026, 5, 28),
        review_type="final",
    )

    assert key == "review:fanvoice:home:today:2026-05-28:final"


def test_fan_voice_review_key_with_player_context():
    """Fan voice review key should work with player context."""
    key = CacheKeyBuilder.fan_voice_review(
        context_type="player",
        context_id="123",
        game_date=date(2026, 5, 28),
        review_type="interim",
    )

    assert key == "review:fanvoice:player:123:2026-05-28:interim"


def test_fan_voice_review_key_convenience_wrapper():
    """Convenience wrapper should match class method."""
    class_key = CacheKeyBuilder.fan_voice_review(
        context_type="home",
        context_id="today",
        game_date=date(2026, 5, 28),
        review_type="final",
    )

    convenience_key = fanvoice_review_key(
        context_type="home",
        context_id="today",
        game_date=date(2026, 5, 28),
        review_type="final",
    )

    assert class_key == convenience_key


def test_team_report_key_format():
    """Team report cache key should follow existing project pattern."""
    key = CacheKeyBuilder.team_report(report_date=date(2026, 5, 28))

    assert key == "report:team:2026-05-28"


def test_player_report_key_format():
    """Player report cache key should follow existing project pattern."""
    key = CacheKeyBuilder.player_report(
        player_id=123,
        report_date=date(2026, 5, 28),
    )

    assert key == "report:player:123:2026-05-28"


def test_cache_keys_use_consistent_namespaces():
    """All cache keys should use consistent namespace prefixes."""
    fanvoice_key = fanvoice_review_key(
        context_type="home",
        context_id="today",
        game_date=date(2026, 5, 28),
        review_type="final",
    )
    team_key = team_report_key(report_date=date(2026, 5, 28))
    player_key = player_report_key(player_id=123, report_date=date(2026, 5, 28))

    # Review namespace
    assert fanvoice_key.startswith("review:")

    # Report namespace (existing pattern)
    assert team_key.startswith("report:")
    assert player_key.startswith("report:")


def test_cache_keys_no_collisions():
    """Different keys should not collide."""
    key1 = fanvoice_review_key(
        context_type="home",
        context_id="today",
        game_date=date(2026, 5, 28),
        review_type="final",
    )
    key2 = fanvoice_review_key(
        context_type="home",
        context_id="today",
        game_date=date(2026, 5, 28),
        review_type="interim",
    )
    key3 = fanvoice_review_key(
        context_type="home",
        context_id="today",
        game_date=date(2026, 5, 27),
        review_type="final",
    )

    # All keys should be unique
    assert key1 != key2  # Different review_type
    assert key1 != key3  # Different game_date
    assert key2 != key3  # Different review_type AND game_date


def test_cache_key_with_date_string():
    """Cache key builder should handle both date objects and strings."""
    key1 = CacheKeyBuilder.fan_voice_review(
        context_type="home",
        context_id="today",
        game_date=date(2026, 5, 28),
        review_type="final",
    )

    key2 = CacheKeyBuilder.fan_voice_review(
        context_type="home",
        context_id="today",
        game_date="2026-05-28",
        review_type="final",
    )

    # Both should produce the same key
    assert key1 == key2
