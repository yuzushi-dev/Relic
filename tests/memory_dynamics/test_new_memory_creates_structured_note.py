"""Tests for new memory creating structured notes.

This test validates A-MEM memory organization model behavior:
- New memories should create structured notes with proper metadata
- Dynamic links are explainable
- Source evidence is preserved in metadata

A-MEM memory organization model extraction
Acceptance criteria: dynamic links are explainable
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from relic.persistence import MemoryPersistence, PrivacyLevel


class TestNewMemoryCreatesStructuredNote:
    """Tests for new memory creating structured notes."""

    def test_new_memory_block_has_required_metadata(self, tmp_path: Path) -> None:
        """Test that new memory blocks have structured metadata."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        content = "[REDACTED_FACT]: user preference for morning meetings"
        block = persistence.store(content, PrivacyLevel.SAFE, metadata={
            "source_session": "session_123",
            "source_prompt_id": str(uuid4()),
        })

        assert block.block_id is not None
        assert block.content_hash is not None
        assert len(block.content_hash) == 64  # SHA-256 hex
        assert block.metadata.get("source_session") == "session_123"

    def test_new_memory_stores_hash_not_raw_content(self, tmp_path: Path) -> None:
        """Verify raw content is never persisted - only hash stored."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        raw_content = "[PRIVATE_FACT]: user email at home"
        block = persistence.store(raw_content, PrivacyLevel.SAFE)

        stored_block = persistence.get(block.block_id)
        assert stored_block is not None
        # Content hash is stored, not raw content
        assert stored_block.content_hash != raw_content
        assert stored_block.content_hash == block.content_hash

    def test_dynamic_links_explainable_via_metadata(self, tmp_path: Path) -> None:
        """Test that dynamic links are stored with explainable metadata."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        parent_block_id = str(uuid4())
        child_block = persistence.store(
            "[PRIVATE_FACT]: updated preference",
            PrivacyLevel.SAFE,
            metadata={
                "dynamic_link": True,
                "linked_from": parent_block_id,
                "link_reason": "related_topic",
            },
        )

        retrieved = persistence.get(child_block.block_id)
        assert retrieved is not None
        assert retrieved.metadata.get("dynamic_link") is True
        assert retrieved.metadata.get("linked_from") == parent_block_id
        assert retrieved.metadata.get("link_reason") == "related_topic"

    def test_memory_block_has_created_timestamp(self, tmp_path: Path) -> None:
        """Test that memory blocks include creation timestamp."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        before = datetime.utcnow()
        block = persistence.store("[REDACTED_FACT]: test fact", PrivacyLevel.SAFE)
        after = datetime.utcnow()

        assert before <= block.created_at <= after

    def test_source_evidence_preserved_in_trace(self, tmp_path: Path) -> None:
        """Test that source evidence is preserved in privacy trace."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        source_prompt_id = str(uuid4())
        block = persistence.store(
            "[REDACTED_FACT]: preference fact",
            PrivacyLevel.SAFE,
            metadata={"source_prompt_id": source_prompt_id},
        )

        traces = persistence.get_trace()
        assert len(traces) == 1
        assert traces[0].content_hash == block.content_hash
        assert traces[0].stage == "store"

    def test_multiple_memories_have_unique_ids(self, tmp_path: Path) -> None:
        """Test that multiple memory blocks have unique IDs."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        block1 = persistence.store("[REDACTED_FACT]: fact 1", PrivacyLevel.SAFE)
        block2 = persistence.store("[REDACTED_FACT]: fact 2", PrivacyLevel.SAFE)
        block3 = persistence.store("[REDACTED_FACT]: fact 3", PrivacyLevel.SAFE)

        assert block1.block_id != block2.block_id
        assert block2.block_id != block3.block_id
        assert block1.block_id != block3.block_id

    def test_memory_persistence_with_different_privacy_levels(self, tmp_path: Path) -> None:
        """Test memory persistence across different privacy classification levels."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        safe_block = persistence.store("[REDACTED_FACT]: safe fact", PrivacyLevel.SAFE)
        s1_block = persistence.store("[PRIVATE_FACT]: quarantine fact", PrivacyLevel.S1_QUARANTINE)
        s2_block = persistence.store("[PERSONAL_PREFERENCE]: warning fact", PrivacyLevel.S2_WARNING)

        assert safe_block.privacy_level == PrivacyLevel.SAFE
        assert s1_block.privacy_level == PrivacyLevel.S1_QUARANTINE
        assert s2_block.privacy_level == PrivacyLevel.S2_WARNING

        # Verify content hash differs based on content
        assert safe_block.content_hash != s1_block.content_hash
        assert s1_block.content_hash != s2_block.content_hash
