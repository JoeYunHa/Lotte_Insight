"""Unit tests for services/article_utils.py."""

import pytest
from services.article_utils import select_primary_label, select_primary_label_and_confidence


class TestSelectPrimaryLabelAndConfidence:
    def test_empty_list(self):
        label, conf = select_primary_label_and_confidence([])
        assert label is None
        assert conf is None

    def test_single_label(self):
        label, conf = select_primary_label_and_confidence([
            {"label": "MATCH_RELATED", "confidence": 0.8}
        ])
        assert label == "MATCH_RELATED"
        assert conf == 0.8

    def test_picks_highest_confidence(self):
        labels = [
            {"label": "ETC", "confidence": 0.3},
            {"label": "MATCH_RELATED", "confidence": 0.9},
            {"label": "INTERVIEW", "confidence": 0.5},
        ]
        label, conf = select_primary_label_and_confidence(labels)
        assert label == "MATCH_RELATED"
        assert conf == 0.9

    def test_none_confidence_treated_as_zero(self):
        labels = [
            {"label": "SECONDARY", "confidence": None},
            {"label": "PRIMARY", "confidence": 0.7},
        ]
        label, conf = select_primary_label_and_confidence(labels)
        assert label == "PRIMARY"

    def test_select_primary_label_delegates(self):
        labels = [
            {"label": "INJURY_ROSTER", "confidence": 0.95},
            {"label": "ETC", "confidence": 0.1},
        ]
        assert select_primary_label(labels) == "INJURY_ROSTER"

    def test_consistency_between_helpers(self):
        """select_primary_label must agree with select_primary_label_and_confidence."""
        labels = [
            {"label": "A", "confidence": 0.6},
            {"label": "B", "confidence": 0.4},
        ]
        label_standalone = select_primary_label(labels)
        label_pair, _ = select_primary_label_and_confidence(labels)
        assert label_standalone == label_pair
