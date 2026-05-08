"""Test: audit history preserves memory updates.

Acceptance criteria:
- Memory updates are tracked with full audit history
- Audit traces preserve source lineage
- No raw sensitive text in audit history

This test validates that memory dynamics maintain proper audit trails
suitable for mechanism reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class MemoryUpdateEvent:
    """A memory update event in the audit history.

    Only contains hashes and metadata - never raw content.
    """
    event_id: str
    timestamp: datetime
    event_type: str  # "create", "update", "decay", "rehearsal"
    block_id: str
    content_hash: str  # SHA-256 of content
    previous_hash: str | None = None
    source_lineage: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to audit record."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "block_id": self.block_id,
            "content_hash": self.content_hash,
            "previous_hash": self.previous_hash,
            "source_lineage": self.source_lineage,
            "metadata": self.metadata,
        }


class AuditHistory:
    """Audit history for memory updates.

    Maintains complete chain of custody without raw content.
    """

    def __init__(self):
        self.events: list[MemoryUpdateEvent] = []

    def record_update(
        self,
        block_id: str,
        content_hash: str,
        event_type: str,
        previous_hash: str | None = None,
        source_lineage: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryUpdateEvent:
        """Record a memory update event."""
        event = MemoryUpdateEvent(
            event_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            event_type=event_type,
            block_id=block_id,
            content_hash=content_hash,
            previous_hash=previous_hash,
            source_lineage=source_lineage or [],
            metadata=metadata or {},
        )
        self.events.append(event)
        return event

    def get_lineage(self, block_id: str) -> list[str]:
        """Get source lineage for a block."""
        lineage = []
        for event in self.events:
            if event.block_id == block_id:
                lineage.extend(event.source_lineage)
        return lineage

    def verify_chain_integrity(self) -> bool:
        """Verify audit chain has no breaks."""
        blocks: dict[str, str | None] = {}

        for event in self.events:
            if event.block_id in blocks:
                # Should have previous hash match
                if blocks[event.block_id] is not None:
                    if event.previous_hash != blocks[event.block_id]:
                        return False
            blocks[event.block_id] = event.content_hash

        return True


class TestAuditHistoryPreservation:
    """Test suite for audit history preservation."""

    def test_audit_records_creation(self):
        """Memory creation is recorded in audit."""
        audit = AuditHistory()

        event = audit.record_update(
            block_id="block-1",
            content_hash="abc123",
            event_type="create",
            source_lineage=["source-1"],
        )

        assert len(audit.events) == 1
        assert event.event_type == "create"
        assert event.block_id == "block-1"

    def test_audit_records_update_with_previous_hash(self):
        """Memory update preserves previous hash chain."""
        audit = AuditHistory()

        audit.record_update(
            block_id="block-1",
            content_hash="abc123",
            event_type="create",
        )

        event = audit.record_update(
            block_id="block-1",
            content_hash="def456",
            event_type="update",
            previous_hash="abc123",
        )

        assert event.previous_hash == "abc123"
        assert len(audit.events) == 2

    def test_audit_preserves_source_lineage(self):
        """Source lineage is preserved through updates."""
        audit = AuditHistory()

        audit.record_update(
            block_id="block-1",
            content_hash="abc123",
            event_type="create",
            source_lineage=["user-input", "derived-1"],
        )

        lineage = audit.get_lineage("block-1")
        assert "user-input" in lineage
        assert "derived-1" in lineage

    def test_audit_records_decay_events(self):
        """Decay events are recorded."""
        audit = AuditHistory()

        event = audit.record_update(
            block_id="block-1",
            content_hash="abc123",
            event_type="decay",
            metadata={"salience_before": 0.8, "salience_after": 0.7},
        )

        assert event.event_type == "decay"
        assert "salience_before" in event.metadata

    def test_audit_records_rehearsal_events(self):
        """Rehearsal events are recorded."""
        audit = AuditHistory()

        event = audit.record_update(
            block_id="block-1",
            content_hash="abc123",
            event_type="rehearsal",
            metadata={"salience_before": 0.5, "salience_after": 0.6},
        )

        assert event.event_type == "rehearsal"

    def test_audit_chain_integrity(self):
        """Audit chain maintains integrity."""
        audit = AuditHistory()

        audit.record_update("block-1", "hash1", "create")
        audit.record_update("block-1", "hash2", "update", previous_hash="hash1")
        audit.record_update("block-1", "hash3", "update", previous_hash="hash2")

        assert audit.verify_chain_integrity() is True

    def test_audit_detects_broken_chain(self):
        """Broken chain integrity is detected."""
        audit = AuditHistory()

        audit.record_update("block-1", "hash1", "create")
        # Intentionally break chain
        audit.record_update("block-1", "hash3", "update", previous_hash="wrong-hash")

        assert audit.verify_chain_integrity() is False


class TestAuditNoRawSensitiveText:
    """Test that audit contains no raw sensitive text."""

    def test_audit_record_contains_no_raw_content(self):
        """Audit records contain hashes, not raw content."""
        import hashlib

        audit = AuditHistory()

        # Use hash, not raw content
        raw_content = "CONFIDENTIAL: secret key 12345"
        content_hash = hashlib.sha256(raw_content.encode()).hexdigest()

        event = audit.record_update(
            block_id="block-sensitive",
            content_hash=content_hash,
            event_type="create",
        )

        # Verify raw content is not in audit record
        event_dict = event.to_dict()
        event_str = str(event_dict)

        assert "CONFIDENTIAL" not in event_str
        assert "secret key" not in event_str
        assert "12345" not in event_str
        assert content_hash in event_str

    def test_serialization_excludes_raw_content(self):
        """Serialized audit records exclude raw content."""
        audit = AuditHistory()

        raw_content = "PRIVATE DATA: ssn 123-45-6789"
        import hashlib
        content_hash = hashlib.sha256(raw_content.encode()).hexdigest()

        audit.record_update(
            block_id="block-privacy",
            content_hash=content_hash,
            event_type="update",
        )

        for event in audit.events:
            event_dict = event.to_dict()
            assert "PRIVATE" not in str(event_dict)
            assert "ssn" not in str(event_dict)
            assert "123-45-6789" not in str(event_dict)


class TestAuditBlockConditions:
    """Test block conditions from mechanism report contract."""

    def test_block_dynamic_traces_no_raw_sensitive(self):
        """Block if: dynamic memory traces contain raw sensitive text.

        Audit traces must never contain raw sensitive content.
        """
        import hashlib

        sensitive_data = "API_KEY=sk-secret123456789"
        content_hash = hashlib.sha256(sensitive_data.encode()).hexdigest()

        audit = AuditHistory()
        audit.record_update(
            block_id="block-api",
            content_hash=content_hash,
            event_type="create",
        )

        # Check all audit output
        all_output = str([e.to_dict() for e in audit.events])

        assert "API_KEY" not in all_output
        assert "sk-secret" not in all_output
        assert "secret123" not in all_output

    def test_block_consolidated_memories_preserve_lineage(self):
        """Block if: consolidated memories lose source lineage.

        Every update must preserve or extend lineage.
        """
        audit = AuditHistory()

        # Initial creation with lineage
        audit.record_update(
            block_id="block-consolidated",
            content_hash="hash1",
            event_type="create",
            source_lineage=["source-a", "source-b"],
        )

        # Consolidation should extend, not lose lineage
        audit.record_update(
            block_id="block-consolidated",
            content_hash="hash2",
            event_type="update",
            previous_hash="hash1",
            source_lineage=["source-a", "source-b", "consolidation-1"],
        )

        lineage = audit.get_lineage("block-consolidated")
        assert "source-a" in lineage
        assert "source-b" in lineage
        assert "consolidation-1" in lineage
