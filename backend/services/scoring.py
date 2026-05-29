"""
Fan Voice Review Scoring Module

Centralized scoring formulas for emotion ranking, player ranking, and opinion
clustering. Module-level functions are the single source of truth; the
`ReviewScoring` class is a thin compatibility shim that exposes the same
formulas as classmethods for callers that prefer the namespaced form.

SQL RPCs use the same formulas but inline for performance — see migration
comments for the matching SQL.
"""

from __future__ import annotations

import math


# Scoring weights (configurable for A/B testing).
PLAYER_REACTION_WEIGHT = 0.2
OPINION_MENTION_WEIGHT = 0.7
OPINION_REACTION_WEIGHT = 0.3


def emotion_score(mention_count: int, reaction_sum: int) -> float:
    """mention_count + ln(1 + reaction_sum) — log dampens viral spikes."""
    return mention_count + math.log1p(reaction_sum)


def player_score(mention_count: int, reaction_sum: int) -> float:
    """mention_count + 0.2 * reaction_sum — reactions are a small boost."""
    return mention_count + PLAYER_REACTION_WEIGHT * reaction_sum


def opinion_score(mention_count: int, reaction_sum: int) -> float:
    """0.7 * mention_count + 0.3 * reaction_sum — balanced cluster ranking."""
    return mention_count * OPINION_MENTION_WEIGHT + reaction_sum * OPINION_REACTION_WEIGHT


class ReviewScoring:
    """Backward-compatible namespace exposing the module-level formulas."""

    PLAYER_REACTION_WEIGHT = PLAYER_REACTION_WEIGHT
    OPINION_MENTION_WEIGHT = OPINION_MENTION_WEIGHT
    OPINION_REACTION_WEIGHT = OPINION_REACTION_WEIGHT

    emotion_score = staticmethod(emotion_score)
    player_score = staticmethod(player_score)
    opinion_score = staticmethod(opinion_score)
