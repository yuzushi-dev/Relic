"""
Tests for Chronicle event type catalogue and helper functions.
"""

import pytest
from relic.chronicle.event_types import (
    EventType,
    EventCategory,
    get_event_type,
    get_event_types_by_category,
    validate_event_type,
    get_catalogue_summary,
    EVENT_TYPE_CATALOGUE,
)


class TestEventTypeCatalogue:
    """Tests for event type catalogue."""

    def test_catalogue_not_empty(self):
        """Test that catalogue has event types."""
        assert len(EVENT_TYPE_CATALOGUE) > 0

    def test_get_event_type_exists(self):
        """Test getting existing event type."""
        et = get_event_type("runtime_received")
        assert et is not None
        assert et.name == "runtime_received"
        assert et.category == EventCategory.RUNTIME

    def test_get_event_type_not_found(self):
        """Test getting non-existing event type."""
        et = get_event_type("nonexistent_event")
        assert et is None

    def test_validate_event_type_valid(self):
        """Test validating valid event type."""
        assert validate_event_type("runtime_received") is True
        assert validate_event_type("output_blocked") is True

    def test_validate_event_type_invalid(self):
        """Test validating invalid event type."""
        assert validate_event_type("invalid_event_xyz") is False

    def test_all_event_types_have_required_fields(self):
        """Test all event types have required fields."""
        for name, et in EVENT_TYPE_CATALOGUE.items():
            assert et.name == name
            assert isinstance(et.category, EventCategory)
            assert et.description
            assert isinstance(et.sensitivity, str)

    def test_event_type_naming_convention(self):
        """Test event types follow snake_case naming."""
        import re
        pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        for name in EVENT_TYPE_CATALOGUE.keys():
            assert pattern.match(name), f"Event type '{name}' violates snake_case"


class TestEventCategories:
    """Tests for event categories."""

    def test_runtime_events(self):
        """Test runtime event category."""
        events = get_event_types_by_category(EventCategory.RUNTIME)
        assert len(events) > 0
        names = [e.name for e in events]
        assert "runtime_received" in names
        assert "identity_resolved" in names

    def test_governance_events(self):
        """Test governance event category."""
        events = get_event_types_by_category(EventCategory.GOVERNANCE)
        assert len(events) > 0
        names = [e.name for e in events]
        assert "context_pack_requested" in names
        assert "context_item_admitted" in names
        assert "context_item_blocked" in names

    def test_output_events(self):
        """Test output event category."""
        events = get_event_types_by_category(EventCategory.OUTPUT)
        assert len(events) > 0
        names = [e.name for e in events]
        assert "output_reviewed" in names
        assert "output_blocked" in names

    def test_identity_events(self):
        """Test identity event category."""
        events = get_event_types_by_category(EventCategory.IDENTITY)
        assert len(events) > 0
        names = [e.name for e in events]
        assert "consent_granted" in names
        assert "consent_revoked" in names

    def test_handoff_events(self):
        """Test handoff event category."""
        events = get_event_types_by_category(EventCategory.HANDOFF)
        assert len(events) > 0
        names = [e.name for e in events]
        assert "handoff_requested" in names
        assert "handoff_authorized" in names
        assert "handoff_blocked" in names

    def test_approval_events(self):
        """Test approval event category."""
        events = get_event_types_by_category(EventCategory.APPROVAL)
        assert len(events) > 0
        names = [e.name for e in events]
        assert "approval_requested" in names
        assert "approval_granted" in names

    def test_cron_events(self):
        """Test cron event category."""
        events = get_event_types_by_category(EventCategory.CRON)
        assert len(events) > 0
        names = [e.name for e in events]
        assert "proactive_checkin_scheduled" in names
        assert "proactive_message_delivered" in names


class TestCatalogueSummary:
    """Tests for catalogue summary."""

    def test_summary_has_total(self):
        """Test summary includes total count."""
        summary = get_catalogue_summary()
        assert "total" in summary
        assert summary["total"] > 0

    def test_summary_has_by_category(self):
        """Test summary includes category breakdown."""
        summary = get_catalogue_summary()
        assert "by_category" in summary
        assert isinstance(summary["by_category"], dict)

    def test_category_counts_match(self):
        """Test category counts match actual events."""
        summary = get_catalogue_summary()
        for category, count in summary["by_category"].items():
            events = get_event_types_by_category(EventCategory(category))
            assert len(events) == count


class TestEventTypePayloadSchema:
    """Tests for event type payload schemas."""

    def test_runtime_received_has_schema(self):
        """Test runtime_received has payload schema."""
        et = get_event_type("runtime_received")
        assert et.payload_schema is not None
        assert "platform" in et.payload_schema

    def test_context_item_admitted_has_schema(self):
        """Test context_item_admitted has payload schema."""
        et = get_event_type("context_item_admitted")
        assert et.payload_schema is not None
        assert "item_type" in et.payload_schema
        assert "item_hash" in et.payload_schema

    def test_output_blocked_has_schema(self):
        """Test output_blocked has payload schema."""
        et = get_event_type("output_blocked")
        assert et.payload_schema is not None
        assert "block_reason" in et.payload_schema
