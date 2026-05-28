"""Tests for centralized scoring module."""

import math

from services.scoring import ReviewScoring, emotion_score, opinion_score, player_score


def test_emotion_score_basic():
    """Emotion score: mention_count + ln(1 + reaction_sum)"""
    # No reactions
    assert emotion_score(10, 0) == 10.0

    # With reactions (log scale)
    result = emotion_score(10, 5)
    expected = 10 + math.log1p(5)  # 10 + ln(6) ≈ 11.79
    assert abs(result - expected) < 0.01


def test_emotion_score_diminishing_returns():
    """Emotion score should show diminishing returns for reactions."""
    # 100 reactions should not double the score
    score_100 = emotion_score(10, 100)
    score_10 = emotion_score(10, 10)

    # ln(101) - ln(11) ≈ 2.22 (much less than 9x difference in reactions)
    assert score_100 < score_10 + 3  # Diminishing returns


def test_player_score_basic():
    """Player score: mention_count + 0.2 * reaction_sum"""
    # No reactions
    assert player_score(10, 0) == 10.0

    # With reactions
    assert player_score(10, 5) == 11.0  # 10 + 0.2 * 5


def test_player_score_weight():
    """Player score should weight reactions at 0.2."""
    assert player_score(10, 10) == 12.0  # 10 + 0.2 * 10
    assert player_score(0, 50) == 10.0  # 0 + 0.2 * 50


def test_opinion_score_basic():
    """Opinion score: mention_count * 0.7 + reaction_sum * 0.3"""
    # No reactions
    assert opinion_score(10, 0) == 7.0  # 10 * 0.7

    # With reactions
    assert opinion_score(10, 10) == 10.0  # 10 * 0.7 + 10 * 0.3


def test_opinion_score_weight_balance():
    """Opinion score should balance mentions (70%) and reactions (30%)."""
    # 10 mentions, 0 reactions = 7.0
    # 0 mentions, 23.33 reactions ≈ 7.0
    assert opinion_score(10, 0) == 7.0
    assert abs(opinion_score(0, int(7.0 / 0.3)) - 7.0) < 0.15  # Allow floating point tolerance


def test_scoring_class_methods():
    """Test ReviewScoring class methods match convenience functions."""
    assert ReviewScoring.emotion_score(10, 5) == emotion_score(10, 5)
    assert ReviewScoring.player_score(10, 5) == player_score(10, 5)
    assert ReviewScoring.opinion_score(10, 5) == opinion_score(10, 5)


def test_scoring_weights_configurable():
    """Test that scoring weights are accessible as class attributes."""
    assert ReviewScoring.PLAYER_REACTION_WEIGHT == 0.2
    assert ReviewScoring.OPINION_MENTION_WEIGHT == 0.7
    assert ReviewScoring.OPINION_REACTION_WEIGHT == 0.3

    # Weights should sum to 1.0 for opinion score
    assert ReviewScoring.OPINION_MENTION_WEIGHT + ReviewScoring.OPINION_REACTION_WEIGHT == 1.0
