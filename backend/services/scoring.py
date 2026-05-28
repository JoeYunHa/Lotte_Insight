"""
Fan Voice Review Scoring Module

Centralized scoring formulas for emotion ranking, player ranking, and opinion clustering.
These formulas are the single source of truth for all review metrics.

SQL RPCs use the same formulas but inline for performance - see migration comments.
"""

from __future__ import annotations

import math


class ReviewScoring:
    """
    Centralized scoring formulas for fan voice review metrics.

    All scoring weights and formulas are defined here to ensure consistency
    across the application and make A/B testing easier.
    """

    # Scoring weights (configurable for A/B testing)
    PLAYER_REACTION_WEIGHT = 0.2
    OPINION_MENTION_WEIGHT = 0.7
    OPINION_REACTION_WEIGHT = 0.3

    @staticmethod
    def emotion_score(mention_count: int, reaction_sum: int) -> float:
        """
        Calculate emotion ranking score.

        Formula: mention_count + ln(1 + reaction_sum)

        Why:
        - Mention count is primary signal (direct mentions)
        - Reaction sum has diminishing returns (log scale)
        - Prevents viral posts from dominating (ln dampening)

        Args:
            mention_count: Number of messages with this emotion tag
            reaction_sum: Total reactions (likes, etc.) across messages

        Returns:
            Float score for ranking emotions
        """
        return mention_count + math.log1p(reaction_sum)

    @staticmethod
    def player_score(mention_count: int, reaction_sum: int) -> float:
        """
        Calculate player mention ranking score.

        Formula: mention_count + 0.2 * reaction_sum

        Why:
        - Mention count is primary signal (player was discussed)
        - Reactions add minor boost (engagement quality)
        - 0.2 weight prevents reaction spam from inflating score

        Args:
            mention_count: Number of mentions for this player
            reaction_sum: Total reactions across mentions

        Returns:
            Float score for ranking players
        """
        return mention_count + ReviewScoring.PLAYER_REACTION_WEIGHT * reaction_sum

    @staticmethod
    def opinion_score(mention_count: int, reaction_sum: int) -> float:
        """
        Calculate opinion cluster score.

        Formula: mention_count * 0.7 + reaction_sum * 0.3

        Why:
        - Cluster size (mention_count) is primary signal (70%)
        - Engagement (reaction_sum) is secondary (30%)
        - Balanced to surface both popular AND engaging opinions

        Args:
            mention_count: Number of messages in this opinion cluster
            reaction_sum: Total reactions across cluster messages

        Returns:
            Float score for ranking opinion clusters
        """
        return (
            mention_count * ReviewScoring.OPINION_MENTION_WEIGHT
            + reaction_sum * ReviewScoring.OPINION_REACTION_WEIGHT
        )


# Convenience functions (backward compatibility)
def emotion_score(mention_count: int, reaction_sum: int) -> float:
    """Calculate emotion score (convenience wrapper)."""
    return ReviewScoring.emotion_score(mention_count, reaction_sum)


def player_score(mention_count: int, reaction_sum: int) -> float:
    """Calculate player score (convenience wrapper)."""
    return ReviewScoring.player_score(mention_count, reaction_sum)


def opinion_score(mention_count: int, reaction_sum: int) -> float:
    """Calculate opinion score (convenience wrapper)."""
    return ReviewScoring.opinion_score(mention_count, reaction_sum)
