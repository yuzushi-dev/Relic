"""Tests for consolidation preserves lineage.

Acceptance criteria:
- consolidated memories preserve source lineage
- mechanism report outputs remain mechanism reports
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from relic.memory_dynamics import MemoryConsolidator, MemoryDynamicsService


class TestConsolidationPreservesLineage:
    """Tests verifying consolidation preserves source lineage."""

    def test_consolidation_preserves_source_lineage(self, tmp_path: Path) -> None:
        """Verify consolidated memories maintain source references."""
        service = MemoryDynamicsService()
        
        values = ["Source A", "Source B", "Source C"]
        result = service.consolidate_memories(
            source_ids=["pref_1", "pref_2", "pref_3"],
            values=values,
            source_type="preference",
        )
        
        assert result is not None
        assert "source_refs" in result
        assert len(result["source_refs"]) == 3

    def test_consolidated_serialization_preserves_lineage(self, tmp_path: Path) -> None:
        """Verify serialized consolidated memory preserves source lineage."""
        consolidator = MemoryConsolidator()
        
        values = ["Source A", "Source B"]
        consolidated = consolidator.consolidate(
            source_ids=["a", "b"],
            source_type="interaction",
            values=values,
        )
        
        serialized = consolidated.to_dict()
        
        assert "source_refs" in serialized
        assert len(serialized["source_refs"]) == 2

    def test_source_lineage_retrievable_after_consolidation(self, tmp_path: Path) -> None:
        """Verify source lineage can be retrieved post-consolidation."""
        consolidator = MemoryConsolidator()
        
        values = ["Memory 1", "Memory 2", "Memory 3"]
        consolidated = consolidator.consolidate(
            source_ids=["m1", "m2", "m3"],
            source_type="correction",
            values=values,
        )
        
        lineage = consolidator.get_source_lineage(consolidated.consolidated_id)
        
        assert len(lineage) == 3
        assert all(ref.original_hash for ref in lineage)

    def test_consolidation_does_not_lose_source_refs(self, tmp_path: Path) -> None:
        """Verify consolidation never loses source references."""
        consolidator = MemoryConsolidator()
        
        round1 = consolidator.consolidate(
            source_ids=["s1", "s2"],
            source_type="preference",
            values=["val1", "val2"],
        )
        
        round2 = consolidator.consolidate(
            source_ids=["s3", "s4"],
            source_type="preference",
            values=["val3", "val4"],
        )
        
        assert len(round1.source_refs) == 2
        assert len(round2.source_refs) == 2

    def test_source_refs_contain_required_fields(self, tmp_path: Path) -> None:
        """Verify source references contain all required fields."""
        consolidator = MemoryConsolidator()
        
        consolidated = consolidator.consolidate(
            source_ids=["test_source"],
            source_type="interaction",
            values=["test_value"],
        )
        
        ref = consolidated.source_refs[0]
        assert ref.source_id == "test_source"
        assert ref.source_type == "interaction"
        assert ref.original_hash is not None
        assert ref.timestamp is not None

    def test_lineage_trace_auditability(self, tmp_path: Path) -> None:
        """Verify source lineage supports audit trail requirements."""
        consolidator = MemoryConsolidator()
        
        values = ["Evidence 1", "Evidence 2", "Evidence 3"]
        consolidated = consolidator.consolidate(
            source_ids=["ev_1", "ev_2", "ev_3"],
            source_type="correction",
            values=values,
        )
        
        for ref in consolidated.source_refs:
            assert ref.source_id.startswith("ev_")
            assert ref.original_hash is not None
            assert len(ref.original_hash) > 0

    def test_privacy_trace_does_not_leak_lineage_sensitive_data(self, tmp_path: Path) -> None:
        """Verify privacy trace doesn't expose sensitive data in lineage."""
        service = MemoryDynamicsService()
        
        sensitive_values = [
            "User email: test@example.com",
            "User phone: 555-123-4567",
        ]
        service.consolidate_memories(
            source_ids=["contact_1", "contact_2"],
            values=sensitive_values,
            source_type="preference",
        )
        
        events = service.get_events()
        event_json = json.dumps([e.to_dict() for e in events])
        
        assert "test@example.com" not in event_json
        assert "555-123-4567" not in event_json
