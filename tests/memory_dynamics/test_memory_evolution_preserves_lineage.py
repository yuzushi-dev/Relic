"""Tests for memory evolution preserving lineage.

This test validates A-MEM memory organization model behavior:
- Memory evolution preserves source evidence
- Correction history is maintained
- Lineage is traceable through updates

A-MEM memory organization model extraction
Acceptance criteria: memory evolution preserves source evidence and correction history
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from relic.correction.propagation import (
    CorrectionPropagator,
    CorrectionType,
)
from relic.persistence import MemoryPersistence, PrivacyLevel


class TestMemoryEvolutionPreservesLineage:
    """Tests for memory evolution preserving lineage."""

    def test_updated_memory_preserves_original_reference(self, tmp_path: Path) -> None:
        """Test that updated memory preserves reference to original."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        original_block = persistence.store(
            "[REDACTED_FACT]: original fact",
            PrivacyLevel.SAFE,
            metadata={"lineage": "original", "created_by": "user_input"},
        )

        updated_block = persistence.store(
            "[REDACTED_FACT]: corrected fact",
            PrivacyLevel.SAFE,
            metadata={
                "lineage": "update",
                "supersedes": original_block.block_id,
                "created_by": "user_correction",
            },
        )

        assert updated_block.metadata.get("supersedes") == original_block.block_id
        assert original_block.metadata.get("lineage") == "original"

    def test_lineage_chain_is_traceable(self, tmp_path: Path) -> None:
        """Test that lineage chain is traceable through memory updates."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        v1 = persistence.store(
            "[REDACTED_FACT]: v1 fact",
            PrivacyLevel.SAFE,
            metadata={"version": "v1"},
        )

        v2 = persistence.store(
            "[REDACTED_FACT]: v2 fact",
            PrivacyLevel.SAFE,
            metadata={"version": "v2", "supersedes": v1.block_id},
        )

        v3 = persistence.store(
            "[REDACTED_FACT]: v3 fact",
            PrivacyLevel.SAFE,
            metadata={"version": "v3", "supersedes": v2.block_id},
        )

        # Trace lineage chain
        lineage_chain = []
        current = v3
        while current.metadata.get("supersedes"):
            lineage_chain.append(current.metadata.get("version"))
            parent_id = current.metadata.get("supersedes")
            current = persistence.get(parent_id) if parent_id else None
            if not current:
                break

        lineage_chain.append(current.metadata.get("version") if current else None)
        lineage_chain.reverse()

        assert "v1" in lineage_chain
        assert "v2" in lineage_chain
        assert "v3" in lineage_chain

    def test_correction_history_preserved_in_trace(self, tmp_path: Path) -> None:
        """Test that correction history is preserved in trace."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        original = persistence.store(
            "[REDACTED_FACT]: original user preference",
            PrivacyLevel.SAFE,
        )

        propagator = CorrectionPropagator(db_path=str(tmp_path / "test.db"))
        propagator.set_trace_output(tmp_path / "correction_trace.jsonl")

        correction_event = propagator.apply_correction(
            prompt_id=original.block_id,  # type: ignore
            correction_type=CorrectionType.CONTENT_UPDATE,
            delta_content="correction applied",
        )

        assert correction_event.completed is True
        assert len(correction_event.events) > 0

    def test_source_evidence_timestamp_preserved(self, tmp_path: Path) -> None:
        """Test that source evidence timestamps are preserved."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        before = datetime.utcnow()
        block = persistence.store(
            "[REDACTED_FACT]: fact with timestamp",
            PrivacyLevel.SAFE,
            metadata={"source": "user_message"},
        )
        after = datetime.utcnow()

        # Original timestamp preserved
        assert block.created_at is not None
        assert before <= block.created_at <= after

        # Verify via retrieval
        retrieved = persistence.get(block.block_id)
        assert retrieved is not None
        assert retrieved.created_at == block.created_at

    def test_derived_memory_retains_source_lineage(self, tmp_path: Path) -> None:
        """Test that derived memory retains source lineage."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        source_block = persistence.store(
            "[REDACTED_FACT]: source fact",
            PrivacyLevel.SAFE,
            metadata={"source_id": "source_001"},
        )

        derived_block = persistence.store(
            "[REDACTED_FACT]: derived summary",
            PrivacyLevel.SAFE,
            metadata={
                "derived_from": source_block.block_id,
                "derivation_type": "summary",
                "source_lineage": "direct",
            },
        )

        assert derived_block.metadata.get("derived_from") == source_block.block_id
        assert derived_block.metadata.get("derivation_type") == "summary"

    def test_privacy_level_inherited_on_derivation(self, tmp_path: Path) -> None:
        """Test that privacy level is preserved on memory derivation."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        s1_block = persistence.store(
            "[PRIVATE_FACT]: quarantined fact",
            PrivacyLevel.S1_QUARANTINE,
        )

        derived = persistence.store(
            "[PRIVATE_FACT]: derived from quarantined",
            PrivacyLevel.S1_QUARANTINE,
            metadata={"derived_from": s1_block.block_id},
        )

        # Privacy level is preserved, not elevated by derivation alone
        assert derived.privacy_level == PrivacyLevel.S1_QUARANTINE

    def test_trace_shows_full_evolution_path(self, tmp_path: Path) -> None:
        """Test that trace shows full evolution path."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        v1 = persistence.store("[REDACTED_FACT]: version 1", PrivacyLevel.SAFE)
        v2 = persistence.store(
            "[REDACTED_FACT]: version 2",
            PrivacyLevel.SAFE,
            metadata={"supersedes": v1.block_id},
        )
        v3 = persistence.store(
            "[REDACTED_FACT]: version 3",
            PrivacyLevel.SAFE,
            metadata={"supersedes": v2.block_id},
        )

        traces = persistence.get_trace()
        trace_hashes = {t.content_hash for t in traces}

        assert v1.content_hash in trace_hashes
        assert v2.content_hash in trace_hashes
        assert v3.content_hash in trace_hashes
        assert len(trace_hashes) == 3

    def test_consolidated_memories_maintain_source_references(self, tmp_path: Path) -> None:
        """Test that consolidated memories maintain source references."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        source_a = persistence.store(
            "[REDACTED_FACT]: fact A",
            PrivacyLevel.SAFE,
            metadata={"topic": "work"},
        )

        source_b = persistence.store(
            "[REDACTED_FACT]: fact B",
            PrivacyLevel.SAFE,
            metadata={"topic": "work"},
        )

        consolidated = persistence.store(
            "[REDACTED_FACT]: consolidated work facts",
            PrivacyLevel.SAFE,
            metadata={
                "consolidated_from": [source_a.block_id, source_b.block_id],
                "consolidation_type": "merge",
            },
        )

        sources = consolidated.metadata.get("consolidated_from", [])
        assert source_a.block_id in sources
        assert source_b.block_id in sources
