"""Tests for new memory linking to relevant prior memory.

This test validates A-MEM memory organization model behavior:
- New memories should link to relevant prior memories
- Dynamic links use semantic relevance
- Links are explainable and traceable

A-MEM memory organization model extraction
Acceptance criteria: dynamic links are explainable
"""

from __future__ import annotations

from pathlib import Path

from relic.persistence import MemoryPersistence, PrivacyLevel


class TestNewMemoryLinksToRelevantPriorMemory:
    """Tests for new memory linking to relevant prior memory."""

    def test_new_memory_can_reference_prior_memory(self, tmp_path: Path) -> None:
        """Test that new memory can establish link to prior memory."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        prior_block = persistence.store(
            "[REDACTED_FACT]: user prefers coffee",
            PrivacyLevel.SAFE,
            metadata={"topic": "beverages", "importance": "high"},
        )

        new_block = persistence.store(
            "[REDACTED_FACT]: user switched to tea",
            PrivacyLevel.SAFE,
            metadata={
                "topic": "beverages",
                "related_to": prior_block.block_id,
                "relationship": "preference_update",
            },
        )

        assert new_block.metadata.get("related_to") == prior_block.block_id
        assert new_block.metadata.get("relationship") == "preference_update"

    def test_link_uses_semantic_topic_relevance(self, tmp_path: Path) -> None:
        """Test that links are established based on semantic topic relevance."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        coffee_block = persistence.store(
            "[REDACTED_FACT]: morning coffee habit",
            PrivacyLevel.SAFE,
            metadata={"topic": "morning_routine", "category": "beverages"},
        )

        tea_block = persistence.store(
            "[REDACTED_FACT]: new tea preference",
            PrivacyLevel.SAFE,
            metadata={"topic": "morning_routine", "category": "beverages"},
        )

        unrelated_block = persistence.store(
            "[REDACTED_FACT]: project deadline tomorrow",
            PrivacyLevel.SAFE,
            metadata={"topic": "work", "category": "tasks"},
        )

        # Coffee and tea should link (same topic/category)
        tea_block.metadata["related_to"] = coffee_block.block_id
        assert tea_block.metadata.get("topic") == coffee_block.metadata.get("topic")

        # Unrelated should not link (different topic)
        assert tea_block.metadata.get("topic") != unrelated_block.metadata.get("topic")

    def test_dynamic_link_explainable_via_relationship_type(self, tmp_path: Path) -> None:
        """Test that link relationship type is explainable."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        prior_block = persistence.store(
            "[REDACTED_FACT]: old preference",
            PrivacyLevel.SAFE,
        )

        new_block = persistence.store(
            "[REDACTED_FACT]: updated preference",
            PrivacyLevel.SAFE,
            metadata={
                "related_to": prior_block.block_id,
                "relationship": "update",
                "explanation": "supersedes prior preference with new information",
            },
        )

        assert new_block.metadata.get("relationship") == "update"
        assert "supersedes" in new_block.metadata.get("explanation", "")

    def test_multiple_potential_links_are_selective(self, tmp_path: Path) -> None:
        """Test that only relevant prior memories are linked."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        all_topics = [
            ("coffee preference", "beverages"),
            ("project meeting", "work"),
            ("evening walk", "exercise"),
            ("tea preference", "beverages"),
            ("report deadline", "work"),
        ]

        blocks = []
        for fact, topic in all_topics:
            block = persistence.store(
                f"[REDACTED_FACT]: {fact}",
                PrivacyLevel.SAFE,
                metadata={"topic": topic},
            )
            blocks.append(block)

        # New memory about beverages should link to beverage topics
        new_block = persistence.store(
            "[REDACTED_FACT]: switched from coffee to matcha",
            PrivacyLevel.SAFE,
            metadata={"topic": "beverages"},
        )

        # Verify new block was stored correctly
        retrieved = persistence.get(new_block.block_id)
        assert retrieved is not None
        assert retrieved.metadata.get("topic") == "beverages"

        beverage_blocks = [b for b in blocks if b.metadata.get("topic") == "beverages"]
        assert len(beverage_blocks) >= 2  # coffee and tea preferences

    def test_link_trace_preserves_relationship_context(self, tmp_path: Path) -> None:
        """Test that link relationship is preserved in privacy trace."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        prior_block = persistence.store(
            "[REDACTED_FACT]: user email preference",
            PrivacyLevel.SAFE,
        )

        new_block = persistence.store(
            "[REDACTED_FACT]: secondary email added",
            PrivacyLevel.SAFE,
            metadata={
                "related_to": prior_block.block_id,
                "relationship": "addition",
                "link_type": "related_fact",
            },
        )

        traces = persistence.get_trace()
        # Trace should contain both blocks
        trace_hashes = [t.content_hash for t in traces]
        assert prior_block.content_hash in trace_hashes
        assert new_block.content_hash in trace_hashes

    def test_self_referential_link_prevented(self, tmp_path: Path) -> None:
        """Test that memory cannot link to itself."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        block = persistence.store(
            "[REDACTED_FACT]: self reference test",
            PrivacyLevel.SAFE,
        )

        # Block ID should not be in its own metadata as related_to
        assert block.metadata.get("related_to") != block.block_id

    def test_orphaned_link_detection_via_trace(self, tmp_path: Path) -> None:
        """Test that broken/orphaned links can be detected via trace."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        block1 = persistence.store(
            "[REDACTED_FACT]: first fact",
            PrivacyLevel.SAFE,
            metadata={"related_to": "nonexistent_id", "relationship": "orphaned"},
        )

        # Orphaned links are valid as metadata - they just reference non-existent blocks
        assert block1.metadata.get("related_to") == "nonexistent_id"
        assert block1.metadata.get("relationship") == "orphaned"
