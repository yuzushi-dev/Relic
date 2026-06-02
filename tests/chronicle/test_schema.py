"""Tests for relic.chronicle.schema, T010."""
from __future__ import annotations

import json
import uuid

import pytest

from relic.chronicle.enums import (
    EventCategory,
    ProximityOrder,
    ReasoningCapture,
    RetentionPolicy,
    Severity,
    ValidationStatus,
    VisibilityLevel,
)
from relic.chronicle.schema import (
    AccessLogEntry,
    Decision,
    Event,
    ProvenanceEdge,
    StateSnapshot,
)

# ---------------------------------------------------------------------------
# Event tests
# ---------------------------------------------------------------------------

class TestEventSchema:
    def test_event_default_fields(self) -> None:
        e = Event(
            event_type="model_called",
            event_category=EventCategory.MODEL,
            source_module="relic.gumi.llm_narrator",
            trace_id=uuid.uuid4(),
        )
        assert e.event_type == "model_called"
        assert e.event_category.value == "model"
        assert e.sensitivity.value == "safe"  # enum value
        assert e.retention_policy == RetentionPolicy.STANDARD_365D
        assert e.visibility == VisibilityLevel.RESEARCHER
        assert e.schema_version == "chronicle-event/v1"

    def test_event_to_db_row(self) -> None:
        tid = uuid.uuid4()
        e = Event(
            event_type="memory_write",
            event_category=EventCategory.MEMORY,
            source_module="hermes.memory_provider",
            trace_id=tid,
            payload={"key": "value", "num": 42},
            input_refs=["event:123", "snapshot:456"],
            tags=["memory:write", "source:provider"],
        )
        row = e.to_db_row()
        assert row["event_id"] == str(e.event_id)
        assert row["trace_id"] == str(tid)
        assert json.loads(row["payload"]) == {"key": "value", "num": 42}
        assert json.loads(row["input_refs"]) == ["event:123", "snapshot:456"]
        assert json.loads(row["tags"]) == ["memory:write", "source:provider"]

    def test_event_to_json(self) -> None:
        e = Event(
            event_type="tool_called",
            event_category=EventCategory.TOOL,
            source_module="test",
            trace_id=uuid.uuid4(),
            payload={"duration_ms": 100},
        )
        j = e.to_json()
        parsed = json.loads(j)
        assert parsed["event_type"] == "tool_called"
        assert parsed["payload"]["duration_ms"] == 100
        assert '"event_type"' in j  # sort_keys applied

    def test_event_invalid_event_type_raises(self) -> None:
        with pytest.raises(ValueError, match="snake_case"):
            Event(
                event_type="InvalidCase",  # uppercase
                event_category=EventCategory.BACKGROUND,
                source_module="test",
                trace_id=uuid.uuid4(),
            )
        with pytest.raises(ValueError, match="snake_case"):
            Event(
                event_type="tool-called",  # kebab-case
                event_category=EventCategory.BACKGROUND,
                source_module="test",
                trace_id=uuid.uuid4(),
            )
        with pytest.raises(ValueError, match="snake_case"):
            Event(
                event_type="123start",  # starts with number
                event_category=EventCategory.BACKGROUND,
                source_module="test",
                trace_id=uuid.uuid4(),
            )

    def test_event_valid_event_type_lowercase_accepted(self) -> None:
        for valid in ["model_called", "memory_write", "a", "test_event_v2", "abc123"]:
            e = Event(
                event_type=valid,
                event_category=EventCategory.BACKGROUND,
                source_module="test",
                trace_id=uuid.uuid4(),
            )
            assert e.event_type == valid

    def test_event_invalid_payload_hash_raises(self) -> None:
        with pytest.raises(ValueError, match="sha256:"):
            Event(
                event_type="test",
                event_category=EventCategory.BACKGROUND,
                source_module="test",
                trace_id=uuid.uuid4(),
                payload_hash="invalid_hash",
            )

    def test_event_valid_payload_hash_accepted(self) -> None:
        e = Event(
            event_type="test",
            event_category=EventCategory.BACKGROUND,
            source_module="test",
            trace_id=uuid.uuid4(),
            payload_hash="sha256:abcdef0123456789",
        )
        assert e.payload_hash == "sha256:abcdef0123456789"

    def test_event_invalid_tag_raises(self) -> None:
        with pytest.raises(ValueError, match="key:value"):
            Event(
                event_type="test",
                event_category=EventCategory.BACKGROUND,
                source_module="test",
                trace_id=uuid.uuid4(),
                tags=["InvalidTag"],  # missing colon
            )

    def test_event_valid_tags_accepted(self) -> None:
        e = Event(
            event_type="test",
            event_category=EventCategory.BACKGROUND,
            source_module="test",
            trace_id=uuid.uuid4(),
            tags=["memory:write", "source:provider", "category:tool"],
        )
        assert len(e.tags) == 3


# ---------------------------------------------------------------------------
# Decision tests
# ---------------------------------------------------------------------------

class TestDecisionSchema:
    def test_decision_default_fields(self) -> None:
        d = Decision(
            decision_kind="tool_selection",
            selected_action={"action_type": "exec", "tool": "bash"},
            actor_type="agent",
            actor_id="hermes",
            trace_id=uuid.uuid4(),
        )
        assert d.decision_kind == "tool_selection"
        assert d.validation_status == ValidationStatus.PENDING
        assert d.schema_version == "chronicle-decision/v1"

    def test_decision_to_db_row(self) -> None:
        tid = uuid.uuid4()
        d = Decision(
            decision_kind="admission",
            selected_action={"action": "allow"},
            rejected_alternatives=[{"action": "block", "reason": "test"}],
            evidence_refs=["event:123"],
            actor_type="rule",
            actor_id="cac",
            trace_id=tid,
        )
        row = d.to_db_row()
        assert row["decision_id"] == str(d.decision_id)
        assert json.loads(row["selected_action"]) == {"action": "allow"}
        assert json.loads(row["rejected_alternatives"]) == [{"action": "block", "reason": "test"}]
        assert json.loads(row["evidence_refs"]) == ["event:123"]

    def test_rationale_summary_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="≤ 280"):
            Decision(
                decision_kind="test",
                selected_action={"a": 1},
                actor_type="agent",
                actor_id="test",
                trace_id=uuid.uuid4(),
                rationale_summary="x" * 281,
            )

    def test_rationale_summary_280_chars_accepted(self) -> None:
        d = Decision(
            decision_kind="test",
            selected_action={"a": 1},
            actor_type="agent",
            actor_id="test",
            trace_id=uuid.uuid4(),
            rationale_summary="x" * 280,
        )
        assert len(d.rationale_summary) == 280


# ---------------------------------------------------------------------------
# StateSnapshot tests
# ---------------------------------------------------------------------------

class TestStateSnapshotSchema:
    def test_snapshot_basic(self) -> None:
        s = StateSnapshot(
            snapshot_type="profile_snapshot",
            content_hash="sha256:abcd1234567890abcdef1234567890ab",
            subject_id="test_subject",
        )
        assert s.snapshot_type == "profile_snapshot"
        assert s.content_hash.startswith("sha256:")
        assert s.snapshot_id is not None

    def test_snapshot_chaining(self) -> None:
        prev_id = uuid.uuid4()
        trigger = uuid.uuid4()
        s = StateSnapshot(
            snapshot_type="memory_state",
            content_hash="sha256:deadbeef1234567890abcdef1234567890ab",
            previous_snapshot_id=prev_id,
            trigger_event_id=trigger,
        )
        assert s.previous_snapshot_id == prev_id
        assert s.trigger_event_id == trigger

    def test_snapshot_to_db_row(self) -> None:
        s = StateSnapshot(
            snapshot_type="engagement",
            content_hash="sha256:abcdef0123456789",
            diff_from_previous={"added": ["x"], "removed": [], "changed": {"y": "z"}},
        )
        row = s.to_db_row()
        assert row["snapshot_id"] == str(s.snapshot_id)
        assert json.loads(row["diff_from_previous"])["added"] == ["x"]


# ---------------------------------------------------------------------------
# ProvenanceEdge tests
# ---------------------------------------------------------------------------

class TestProvenanceEdgeSchema:
    def test_edge_basic(self) -> None:
        tid = uuid.uuid4()
        aid = uuid.uuid4()
        e = ProvenanceEdge(
            trace_id=tid,
            artifact_id=aid,
            from_node_type="event",
            from_node_id=uuid.uuid4(),
            relation=ProximityOrder.USED,
        )
        assert e.relation == ProximityOrder.USED

    def test_edge_all_relations(self) -> None:
        for rel in ProximityOrder:
            e = ProvenanceEdge(
                trace_id=uuid.uuid4(),
                artifact_id=uuid.uuid4(),
                from_node_type="event",
                from_node_id=uuid.uuid4(),
                relation=rel,
            )
            assert e.relation == rel


# ---------------------------------------------------------------------------
# AccessLogEntry tests
# ---------------------------------------------------------------------------

class TestAccessLogEntrySchema:
    def test_access_log_basic(self) -> None:
        a = AccessLogEntry(
            accessor_id="researcher:cristina",
            access_kind="query",
            target_filter={"subject_id": "test_subj"},
            rows_returned=42,
        )
        assert a.accessor_id == "researcher:cristina"
        assert a.rows_returned == 42

    def test_access_log_to_db_row(self) -> None:
        a = AccessLogEntry(
            accessor_id="system",
            access_kind="export",
            target_filter={"subject_id": "X", "category": "memory"},
        )
        row = a.to_db_row()
        assert json.loads(row["target_filter"]) == {"subject_id": "X", "category": "memory"}


# ---------------------------------------------------------------------------
# Enum roundtrip tests
# ---------------------------------------------------------------------------

class TestEnumRoundtrip:
    def test_event_category_serialization(self) -> None:
        e = Event(
            event_type="test",
            event_category=EventCategory.ERROR,
            source_module="test",
            trace_id=uuid.uuid4(),
        )
        assert e.event_category.value == "error"
        j = e.to_json()
        assert '"error"' in j.lower()

    def test_visibility_level_serialization(self) -> None:
        e = Event(
            event_type="test",
            event_category=EventCategory.ADMIN,
            source_module="test",
            trace_id=uuid.uuid4(),
            visibility=VisibilityLevel.SUBJECT_EXPORT,
        )
        assert e.visibility == VisibilityLevel.SUBJECT_EXPORT

    def test_retention_policy_serialization(self) -> None:
        s = StateSnapshot(
            snapshot_type="test",
            content_hash="sha256:abcdef0123456789",
            retention_policy=RetentionPolicy.LEGAL_HOLD,
        )
        assert s.retention_policy == RetentionPolicy.LEGAL_HOLD
        assert s.to_db_row()["retention_policy"] == "legal_hold"
