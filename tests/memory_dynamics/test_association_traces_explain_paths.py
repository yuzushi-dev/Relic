"""Tests for association traces explain paths.

Acceptance criteria:
- association traces can explain activation paths
- mechanism report outputs remain mechanism reports
"""

from __future__ import annotations

from relic.memory_dynamics import AssociationTracer


class TestAssociationTracesExplainPaths:
    """Tests verifying association traces explain activation paths."""

    def test_record_association(self) -> None:
        """Test recording an association between memories."""
        tracer = AssociationTracer()
        
        record = tracer.record_association(
            source_id="memory-1",
            target_id="memory-2",
            association_type="semantic",
            strength=0.8,
        )
        
        assert record["source_hash"] is not None
        assert record["target_hash"] is not None
        assert record["association_type"] == "semantic"
        assert record["strength"] == 0.8

    def test_get_associations_by_source(self) -> None:
        """Test retrieving associations filtered by source."""
        tracer = AssociationTracer()
        
        tracer.record_association("source-1", "target-1", "related")
        tracer.record_association("source-1", "target-2", "similar")
        tracer.record_association("source-2", "target-3", "different")
        
        associations = tracer.get_associations("source-1")
        
        assert len(associations) == 2
        for assoc in associations:
            assert assoc["source_hash"] == associations[0]["source_hash"]

    def test_explain_path(self) -> None:
        """Test explaining an activation path."""
        tracer = AssociationTracer()
        
        tracer.record_association("A", "B", "causal", strength=0.9)
        tracer.record_association("B", "C", "sequential", strength=0.7)
        
        path = tracer.explain_path(["A", "B", "C"])
        
        assert len(path) == 2

    def test_association_trace_contains_only_hashes(self) -> None:
        """Test that association traces contain only hashes."""
        tracer = AssociationTracer()
        
        tracer.record_association(
            source_id="user-email-personal",
            target_id="secure-data",
            association_type="contains",
        )
        
        associations = tracer.get_associations()
        assoc_str = str(associations)
        
        # Should not contain raw identifiers
        assert "user-email" not in assoc_str
        assert "secure-data" not in assoc_str
        
        # Should contain hash values (hex strings of sufficient length)
        for assoc in associations:
            assert len(assoc["source_hash"]) >= 8
            assert len(assoc["target_hash"]) >= 8

    def test_multiple_associations_are_independent(self) -> None:
        """Test that multiple associations are tracked independently."""
        tracer = AssociationTracer()
        
        tracer.record_association("s1", "t1", "type-a")
        tracer.record_association("s2", "t2", "type-b")
        tracer.record_association("s3", "t3", "type-c")
        
        all_assocs = tracer.get_associations()
        assert len(all_assocs) == 3
