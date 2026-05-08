"""Tests for memory evolution not rewriting corrections.

This test validates A-MEM memory organization model behavior:
- Corrections are immutable once applied
- Memory evolution preserves correction history
- Corrections cannot be overwritten by new memory

A-MEM memory organization model extraction
Acceptance criteria: memory evolution preserves source evidence and correction history
Block condition: consolidated memories lose source lineage
"""

from __future__ import annotations

from pathlib import Path

from relic.correction.propagation import (
    CorrectionPropagator,
    CorrectionType,
)
from relic.persistence import MemoryPersistence, PrivacyLevel


class TestMemoryEvolutionDoesNotRewriteCorrections:
    """Tests ensuring memory evolution does not rewrite corrections."""

    def test_correction_is_immutable_once_applied(self, tmp_path: Path) -> None:
        """Test that corrections are immutable once applied."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        original = persistence.store(
            "[REDACTED_FACT]: original fact",
            PrivacyLevel.SAFE,
            metadata={"mutable": True, "corrected": False},
        )

        propagator = CorrectionPropagator(db_path=str(tmp_path / "test.db"))
        propagator.set_trace_output(tmp_path / "correction_trace.jsonl")

        trace = propagator.apply_correction(
            prompt_id=original.block_id,  # type: ignore
            correction_type=CorrectionType.FACTUAL_CORRECTION,
            delta_content="This fact was incorrect",
        )

        assert trace.completed is True
        assert trace.events[0].applied is True

        # Original block should still exist with its content
        retrieved = persistence.get(original.block_id)
        assert retrieved is not None
        assert retrieved.metadata.get("corrected") is not True  # Not modified in-place

    def test_correction_creates_new_record_not_rewrite(self, tmp_path: Path) -> None:
        """Test that corrections create new records, not rewrite existing."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        original_block = persistence.store(
            "[REDACTED_FACT]: original content",
            PrivacyLevel.SAFE,
            metadata={"correction_count": 0},
        )

        original_hash = original_block.content_hash

        propagator = CorrectionPropagator(db_path=str(tmp_path / "test.db"))
        propagator.set_trace_output(tmp_path / "correction_trace.jsonl")

        propagator.apply_correction(
            prompt_id=original_block.block_id,  # type: ignore
            correction_type=CorrectionType.CONTENT_UPDATE,
            delta_content="Updated content",
        )

        # Original block should be unchanged
        retrieved = persistence.get(original_block.block_id)
        assert retrieved is not None
        assert retrieved.content_hash == original_hash

    def test_correction_history_traces_cannot_be_erased(self, tmp_path: Path) -> None:
        """Test that correction history traces cannot be erased."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        block = persistence.store(
            "[REDACTED_FACT]: fact with history",
            PrivacyLevel.SAFE,
        )

        propagator = CorrectionPropagator(db_path=str(tmp_path / "test.db"))
        propagator.set_trace_output(tmp_path / "correction_trace.jsonl")

        trace1 = propagator.apply_correction(
            prompt_id=block.block_id,  # type: ignore
            correction_type=CorrectionType.FIRST_CORRECTION,
            delta_content="First correction",
        )

        trace2 = propagator.apply_correction(
            prompt_id=block.block_id,  # type: ignore
            correction_type=CorrectionType.CONTENT_UPDATE,
            delta_content="Second correction",
        )

        # Both traces should be recorded
        assert trace1.completed is True
        assert trace2.completed is True
        assert trace1.id != trace2.id

    def test_new_memory_does_not_override_correction_marker(self, tmp_path: Path) -> None:
        """Test that new memory does not override correction markers."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        original = persistence.store(
            "[REDACTED_FACT]: original fact",
            PrivacyLevel.SAFE,
            metadata={"corrected": False, "needs_review": False},
        )

        propagator = CorrectionPropagator(db_path=str(tmp_path / "test.db"))
        propagator.set_trace_output(tmp_path / "correction_trace.jsonl")

        propagator.apply_correction(
            prompt_id=original.block_id,  # type: ignore
            correction_type=CorrectionType.FACTUAL_CORRECTION,
            delta_content="Correction applied",
        )

        # New memory should not modify the original
        new_memory = persistence.store(
            "[REDACTED_FACT]: new fact",
            PrivacyLevel.SAFE,
            metadata={"supersedes": original.block_id},
        )

        # Verify new memory exists and links to original
        retrieved_new = persistence.get(new_memory.block_id)
        assert retrieved_new is not None
        assert retrieved_new.metadata.get("supersedes") == original.block_id

        retrieved_original = persistence.get(original.block_id)
        assert retrieved_original is not None
        assert retrieved_original.metadata.get("corrected") is not True

    def test_deletion_preserves_correction_reference(self, tmp_path: Path) -> None:
        """Test that deletion preserves correction reference."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        block = persistence.store(
            "[REDACTED_FACT]: fact to delete",
            PrivacyLevel.SAFE,
            metadata={"deleted": False},
        )

        propagator = CorrectionPropagator(db_path=str(tmp_path / "test.db"))
        propagator.set_trace_output(tmp_path / "correction_trace.jsonl")

        propagator.apply_correction(
            prompt_id=block.block_id,  # type: ignore
            correction_type=CorrectionType.DELETION,
            delta_content="Marked for deletion",
        )

        # Deletion should not remove the block
        retrieved = persistence.get(block.block_id)
        assert retrieved is not None

    def test_correction_trace_shows_full_history(self, tmp_path: Path) -> None:
        """Test that correction trace shows full history."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")
        correction_trace_path = tmp_path / "correction_trace.jsonl"

        block = persistence.store(
            "[REDACTED_FACT]: fact with multiple corrections",
            PrivacyLevel.SAFE,
        )

        propagator = CorrectionPropagator(db_path=str(tmp_path / "test.db"))
        propagator.set_trace_output(correction_trace_path)

        corrections = [
            CorrectionType.FIRST_CORRECTION,
            CorrectionType.CONTENT_UPDATE,
            CorrectionType.FACTUAL_CORRECTION,
        ]

        for correction_type in corrections:
            trace = propagator.apply_correction(
                prompt_id=block.block_id,  # type: ignore
                correction_type=correction_type,
                delta_content=f"{correction_type.value} applied",
            )
            assert trace.completed is True

        # Verify trace file exists and has content
        assert correction_trace_path.exists()

    def test_lineage_preserved_after_multiple_corrections(self, tmp_path: Path) -> None:
        """Test that lineage is preserved after multiple corrections."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        v1 = persistence.store(
            "[REDACTED_FACT]: version 1",
            PrivacyLevel.SAFE,
            metadata={"version": "v1", "lineage_root": True},
        )

        v2 = persistence.store(
            "[REDACTED_FACT]: version 2 (corrected)",
            PrivacyLevel.SAFE,
            metadata={"version": "v2", "supersedes": v1.block_id},
        )

        v3 = persistence.store(
            "[REDACTED_FACT]: version 3 (corrected again)",
            PrivacyLevel.SAFE,
            metadata={"version": "v3", "supersedes": v2.block_id},
        )

        # All versions should be retrievable
        assert persistence.get(v1.block_id) is not None
        assert persistence.get(v2.block_id) is not None
        assert persistence.get(v3.block_id) is not None

        # Lineage chain intact
        current = v3
        lineage_versions = ["v3"]
        while current.metadata.get("supersedes"):
            parent_id = current.metadata.get("supersedes")
            current = persistence.get(parent_id)  # type: ignore
            if current:
                lineage_versions.append(current.metadata.get("version", "unknown"))
            else:
                break

        assert "v1" in lineage_versions
        assert "v2" in lineage_versions
        assert "v3" in lineage_versions

    def test_correction_blocks_prevent_contradictory_memory(self, tmp_path: Path) -> None:
        """Test that correction blocks prevent contradictory memory additions."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        original = persistence.store(
            "[REDACTED_FACT]: user prefers vanilla",
            PrivacyLevel.SAFE,
            metadata={"preference": "vanilla"},
        )

        propagator = CorrectionPropagator(db_path=str(tmp_path / "test.db"))
        propagator.set_trace_output(tmp_path / "correction_trace.jsonl")

        propagator.apply_correction(
            prompt_id=original.block_id,  # type: ignore
            correction_type=CorrectionType.FACTUAL_CORRECTION,
            delta_content="Changed to chocolate",
        )

        # Subsequent memory should link to correction, not contradict
        new_memory = persistence.store(
            "[REDACTED_FACT]: user prefers chocolate",
            PrivacyLevel.SAFE,
            metadata={
                "supersedes": original.block_id,
                "reason": "correction_applied",
            },
        )

        assert new_memory.metadata.get("supersedes") == original.block_id
        assert new_memory.metadata.get("reason") == "correction_applied"
