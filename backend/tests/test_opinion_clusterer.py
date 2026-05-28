from services.opinion_clusterer import OpinionClusterer


def test_cluster_by_jaccard_trigram_groups_similar_messages():
    clusterer = OpinionClusterer(similarity_threshold=0.5, min_cluster_size=2)
    messages = [
        {"id": "1", "message": "불펜 운용 아쉽다", "reaction_count": 3, "emotion_tag": "frustrated"},
        {"id": "2", "message": "불펜 운용 너무 아쉽다", "reaction_count": 1, "emotion_tag": "disappointed"},
        {"id": "3", "message": "타선 좋아서 기대된다", "reaction_count": 4, "emotion_tag": "hopeful"},
    ]
    result = clusterer.cluster_by_jaccard_trigram(messages, max_opinions=5)
    assert len(result) == 1
    assert result[0]["mention_count"] == 2
    assert result[0]["reaction_sum"] == 4


def test_cluster_drops_singleton_when_min_cluster_size_is_two():
    clusterer = OpinionClusterer(similarity_threshold=0.9, min_cluster_size=2)
    messages = [
        {"id": "1", "message": "A"},
        {"id": "2", "message": "B"},
    ]
    result = clusterer.cluster_by_jaccard_trigram(messages)
    assert result == []


# Validation tests (Issue #7: Defensive validation)


def test_cluster_validates_required_fields():
    """Clusterer should raise ValueError if messages missing 'id' field."""
    clusterer = OpinionClusterer()
    invalid_messages = [
        {"message": "Test message", "reaction_count": 0},  # Missing 'id'
    ]

    try:
        clusterer.cluster_by_jaccard_trigram(invalid_messages)
        assert False, "Should have raised ValueError for missing 'id' field"
    except ValueError as e:
        assert "missing required fields" in str(e).lower()
        assert "id" in str(e)


def test_cluster_validates_message_type():
    """Clusterer should raise ValueError if messages are not dictionaries."""
    clusterer = OpinionClusterer()
    invalid_messages = [
        "not a dictionary",  # Wrong type
    ]

    try:
        clusterer.cluster_by_jaccard_trigram(invalid_messages)
        assert False, "Should have raised ValueError for non-dict message"
    except ValueError as e:
        assert "not a dictionary" in str(e).lower()


def test_cluster_validates_text_content():
    """Clusterer should raise ValueError if no messages have text content."""
    clusterer = OpinionClusterer()
    invalid_messages = [
        {"id": "1", "reaction_count": 5},  # No 'message' or 'normalized_message'
        {"id": "2", "reaction_count": 3},
    ]

    try:
        clusterer.cluster_by_jaccard_trigram(invalid_messages)
        assert False, "Should have raised ValueError for missing text content"
    except ValueError as e:
        assert "no messages with text content" in str(e).lower()


def test_cluster_validates_reaction_count_type():
    """Clusterer should raise ValueError if reaction_count is invalid."""
    clusterer = OpinionClusterer()
    invalid_messages = [
        {"id": "1", "message": "Test", "reaction_count": "invalid"},  # Can't convert to int
    ]

    try:
        clusterer.cluster_by_jaccard_trigram(invalid_messages)
        assert False, "Should have raised ValueError for invalid reaction_count"
    except ValueError as e:
        assert "invalid reaction_count" in str(e).lower()


def test_cluster_handles_empty_list():
    """Clusterer should gracefully handle empty message list."""
    clusterer = OpinionClusterer()
    result = clusterer.cluster_by_jaccard_trigram([])
    assert result == []


def test_cluster_accepts_coercible_reaction_count():
    """Clusterer should accept string numbers for reaction_count."""
    clusterer = OpinionClusterer()
    messages = [
        {"id": "1", "message": "Test 1", "reaction_count": "5"},  # String but coercible
        {"id": "2", "message": "Test 2", "reaction_count": "3"},
    ]

    # Should not raise (coercible types are okay)
    result = clusterer.cluster_by_jaccard_trigram(messages)
    # Won't cluster (different messages, high threshold)
    assert isinstance(result, list)
