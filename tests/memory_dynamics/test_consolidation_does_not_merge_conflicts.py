"""Tests for consolidation does not merge conflicts.

Acceptance criteria:
- consolidation does not merge conflicting memories
- mechanism report outputs remain mechanism reports
"""

from __future__ import annotations

import pytest

from relic.memory_dynamics import MemoryConsolidator, MemoryDynamicsService


class TestConsolidationDoesNotMergeConflicts:
    """Tests verifying consolidation doesn't merge conflicting memories."""

    def test_consolidation_with_different_corrections(self) -> None:
        """Test that memories with different corrections are not merged."""
        consolidator = MemoryConsolidator()
        
        # Two memories that might conflict
        values = ["Fact A", "Fact B"]
        consolidated = consolidator.consolidate(
            source_ids=["fact_a", "fact_b"],
            source_type="interaction",
            values=values,
        )
        
        # Should have separate source refs
        assert len(consolidated.source_refs) == 2
        
        # Original hashes should be different
        hashes = [ref.original_hash for ref in consolidated.source_refs]
        assert len(set(hashes)) == 2

    def test_consolidation_preserves_individual_source_refs(self) -> None:
        """Test that individual source refs are preserved after consolidation."""
        consolidator = MemoryConsolidator()
        
        consolidated = consolidator.consolidate(
            source_ids=["src1", "src2", "src3"],
            source_type="preference",
            values=["pref1", "pref2", "pref3"],
        )
        
        # Each source should have its own ref
        source_ids = [ref.source_id for ref in consolidated.source_refs]
        assert "src1" in source_ids
        assert "src2" in source_ids
        assert "src3" in source_ids

    def test_empty_consolidation_returns_empty_refs(self) -> None:
        """Test consolidation with no sources returns empty refs."""
        consolidator = MemoryConsolidator()
        
        consolidated = consolidator.consolidate(
            source_ids=[],
            source_type="interaction",
            values=[],
        )
        
        assert len(consolidated.source_refs) == 0

    def test_single_source_consolidation(self) -> None:
        """Test consolidation of single source preserves ref."""
        consolidator = MemoryConsolidator()
        
        consolidated = consolidator.consolidate(
            source_ids=["single"],
            source_type="preference",
            values=["single_value"],
        )
        
        assert len(consolidated.source_refs) == 1
        assert consolidated.source_refs[0].source_id == "single"
