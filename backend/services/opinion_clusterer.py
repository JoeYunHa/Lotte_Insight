from __future__ import annotations

from collections import Counter

from services.scoring import opinion_score


class OpinionClusterer:
    """
    Opinion clustering engine with defensive validation.

    Performs Jaccard + trigram similarity-based clustering on fan messages.
    Validates input data to prevent crashes from malformed API contracts.
    """

    # Required fields for clustering (strict validation)
    REQUIRED_FIELDS = frozenset({"id"})

    # Optional but recommended fields (warning if missing)
    RECOMMENDED_FIELDS = frozenset({"message", "normalized_message", "reaction_count"})

    def __init__(self, *, similarity_threshold: float = 0.65, min_cluster_size: int = 2):
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size

    def cluster_by_jaccard_trigram(self, messages: list[dict], *, max_opinions: int = 5) -> list[dict]:
        """
        Cluster messages by Jaccard + trigram similarity.

        Args:
            messages: List of message dictionaries
            max_opinions: Maximum number of top opinions to return

        Returns:
            List of opinion cluster dictionaries, sorted by score descending

        Raises:
            ValueError: If messages contain invalid or missing required fields
        """
        if not messages:
            return []

        # Defensive validation (prevent production crashes)
        self._validate_messages(messages)
        normalized = [self._prepare_message(item) for item in messages]
        clusters: list[list[dict]] = []

        for item in normalized:
            # Assign to the highest-similarity cluster above the threshold,
            # not just the first match found (prevents drift on near-ties).
            best_index = -1
            best_score = self.similarity_threshold
            for idx, cluster in enumerate(clusters):
                centroid = cluster[0]["_trigrams"]
                score = self._jaccard_similarity(centroid, item["_trigrams"])
                if score > best_score:
                    best_score = score
                    best_index = idx
            if best_index >= 0:
                clusters[best_index].append(item)
            else:
                clusters.append([item])

        ranked: list[dict] = []
        cluster_idx = 0
        for cluster in clusters:
            if len(cluster) < self.min_cluster_size:
                continue
            cluster_idx += 1
            representative = max(cluster, key=lambda m: (m.get("reaction_count", 0), len(m["_text"])))
            mention_count = len(cluster)
            reaction_sum = sum(int(x.get("reaction_count", 0) or 0) for x in cluster)
            # Use centralized scoring formula (single source of truth)
            score = opinion_score(mention_count, reaction_sum)
            sentiment_hint = self._infer_sentiment([x.get("emotion_tag") for x in cluster if x.get("emotion_tag")])
            primary_player_id = self._mode([x.get("primary_player_id") for x in cluster if x.get("primary_player_id")])
            ranked.append(
                {
                    "cluster_key": f"c{cluster_idx}",
                    "opinion_title": representative["_text"][:20] + ("..." if len(representative["_text"]) > 20 else ""),
                    "representative_message": representative["_text"],
                    "mention_count": mention_count,
                    "reaction_sum": reaction_sum,
                    "score": score,
                    "sentiment_hint": sentiment_hint,
                    "primary_player_id": primary_player_id,
                    "evidence_message_ids": [x["id"] for x in cluster if x.get("id")],
                    "evidence_count": mention_count,
                }
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:max_opinions]

    def _prepare_message(self, message: dict) -> dict:
        text = str(message.get("normalized_message") or message.get("message") or "").strip().lower()
        return {**message, "_text": text, "_trigrams": set(self._trigrams(text))}

    @staticmethod
    def _trigrams(text: str) -> list[str]:
        if not text:
            return []
        if len(text) < 3:
            return [text]
        return [text[i : i + 3] for i in range(len(text) - 2)]

    @staticmethod
    def _jaccard_similarity(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    @staticmethod
    def _mode(items: list[int]) -> int | None:
        if not items:
            return None
        return Counter(items).most_common(1)[0][0]

    @staticmethod
    def _infer_sentiment(emotions: list[str]) -> str:
        positive = {"excited", "hopeful", "proud"}
        negative = {"frustrated", "disappointed", "angry"}
        p = sum(1 for e in emotions if e in positive)
        n = sum(1 for e in emotions if e in negative)
        if p > n * 1.5:
            return "positive"
        if n > p * 1.5:
            return "negative"
        if abs(p - n) <= 1:
            return "mixed"
        return "neutral"

    def _validate_messages(self, messages: list[dict]) -> None:
        """
        Validate message structure (defensive programming).

        Checks:
        1. Required fields present in all messages
        2. At least one message has text content
        3. No obviously malformed data (e.g., negative reaction counts)

        Args:
            messages: List of message dictionaries to validate

        Raises:
            ValueError: If validation fails with detailed error message
        """
        if not messages:
            return  # Empty list is valid (handled by caller)

        # Sample first few messages for validation (performance trade-off)
        sample_size = min(5, len(messages))
        sample = messages[:sample_size]

        # Check 1: Required fields present
        for i, msg in enumerate(sample):
            if not isinstance(msg, dict):
                raise ValueError(f"Message at index {i} is not a dictionary: {type(msg)}")

            missing_fields = self.REQUIRED_FIELDS - msg.keys()
            if missing_fields:
                raise ValueError(
                    f"Message at index {i} missing required fields: {missing_fields}. "
                    f"Available fields: {set(msg.keys())}"
                )

        # Check 2: At least one message has text content
        has_text = any(
            msg.get("message") or msg.get("normalized_message")
            for msg in sample
        )
        if not has_text:
            raise ValueError(
                "No messages with text content found. "
                "At least one of 'message' or 'normalized_message' must be present."
            )

        # Check 3: Reaction count sanity check (warn but don't fail)
        for i, msg in enumerate(sample):
            reaction_count = msg.get("reaction_count")
            if reaction_count is not None and not isinstance(reaction_count, (int, float)):
                # Coercible types are okay (e.g., "5" as string)
                try:
                    int(reaction_count)
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"Message at index {i} has invalid reaction_count: "
                        f"{reaction_count!r} (type: {type(reaction_count)})"
                    ) from e
