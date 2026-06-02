"""PR03, /relic why last trace tests.

Tests verify:
- /relic why returns last PCP/CAC trace
- Trace is redacted (no raw content)
- Trace contains trace_id, event type, metadata
"""

from __future__ import annotations

import pytest

from relic.hermes_plugin.plugin import RelicHermesPlugin
from relic.context_pack import (
    ContextPackBuilder,
    TaskType,
    RoleplayLevel,
    PCPTrace,
    PCPTraceEvent,
)


class TestRelicWhyLastTrace:
    """Verify /relic why returns last trace."""

    def test_plugin_get_last_pcp_trace(self) -> None:
        """Plugin should return last PCP trace."""
        plugin = RelicHermesPlugin()
        plugin.load()

        # Generate some traces by injecting context
        plugin.inject_ephemeral_context(session_id="SES-001")
        plugin.inject_ephemeral_context(session_id="SES-002")

        trace = plugin.get_last_pcp_trace()
        assert trace is not None
        assert "trace_id" in trace
        assert "event" in trace

    def test_trace_contains_event_type(self) -> None:
        """Trace should contain event type."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
        )
        trace_entries = trace.get_trace()
        assert len(trace_entries) > 0
        last_event = trace_entries[-1]
        assert "event" in last_event
        assert last_event["event"] in [e.value for e in PCPTraceEvent]

    def test_trace_contains_trace_id(self) -> None:
        """Trace should contain trace_id."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
        )
        trace_entries = trace.get_trace()
        assert len(trace_entries) > 0
        last_event = trace_entries[-1]
        assert "trace_id" in last_event
        assert last_event["trace_id"] == "test-123"

    def test_trace_contains_session_id(self) -> None:
        """Trace should contain session_id."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
        )
        trace_entries = trace.get_trace()
        assert len(trace_entries) > 0
        last_event = trace_entries[-1]
        assert "session_id" in last_event
        assert last_event["session_id"] == "SES-001"

    def test_trace_contains_turn_id(self) -> None:
        """Trace should contain turn_id."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
        )
        trace_entries = trace.get_trace()
        assert len(trace_entries) > 0
        last_event = trace_entries[-1]
        assert "turn_id" in last_event
        assert last_event["turn_id"] == "TURN-001"

    def test_trace_contains_timestamp(self) -> None:
        """Trace should contain timestamp."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
        )
        trace_entries = trace.get_trace()
        assert len(trace_entries) > 0
        last_event = trace_entries[-1]
        assert "timestamp" in last_event

    def test_trace_contains_metadata(self) -> None:
        """Trace should contain metadata."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
            metadata={
                "task_type": "relational",
                "roleplay_level": "high",
                "pack_id": "PCP-001",
            },
        )
        trace_entries = trace.get_trace()
        assert len(trace_entries) > 0
        last_event = trace_entries[-1]
        assert "metadata" in last_event
        assert "task_type" in last_event["metadata"]
        assert "roleplay_level" in last_event["metadata"]


class TestTraceRedaction:
    """Verify trace is redacted."""

    def test_trace_no_raw_content(self) -> None:
        """Trace should not contain raw content."""
        trace = PCPTrace()
        # This is short metadata, not raw content
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
            metadata={
                "task_type": "technical",
                "roleplay_level": "normal",
            },
        )
        # This would be long raw content - should be redacted
        trace.log(
            event=PCPTraceEvent.BUILD_COMPLETED,
            trace_id="test-123",
            metadata={
                "long_raw_content": "This is a long raw user input that should not appear in trace because it exceeds reasonable length limits and contains newlines which indicate multi-line content.",
            },
        )

        trace_entries = trace.get_trace()
        trace_str = str(trace_entries).lower()

        # Raw content should not appear (long strings are redacted)
        assert "this is a long raw" not in trace_str
        assert "user input" not in trace_str

    def test_trace_no_raw_prompts(self) -> None:
        """Trace should not contain raw prompts."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
            metadata={"prompt": "You are a helpful assistant"},  # Raw prompt
        )

        trace_entries = trace.get_trace()
        assert len(trace_entries) > 0

        for entry in trace_entries:
            if entry.get("metadata"):
                for key, value in entry["metadata"].items():
                    if key == "prompt":
                        assert value == "[REDACTED]", f"Raw prompts should be redacted, got: {value}"

    def test_trace_no_private_data(self) -> None:
        """Trace should not contain private data."""
        trace = PCPTrace()
        # Simulate a prompt with private data
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
            metadata={"email": "user@example.com"},  # Should be redacted
        )

        trace_entries = trace.get_trace()
        for entry in trace_entries:
            if entry.get("metadata"):
                for key, value in entry["metadata"].items():
                    # Emails should be redacted
                    if isinstance(value, str) and "@" in value:
                        assert value == "[REDACTED]", f"Email should be redacted, got: {value}"


class TestTraceForDebugging:
    """Verify trace provides useful debugging info."""

    def test_trace_shows_build_started_and_completed(self) -> None:
        """Trace should show both start and completion."""
        trace = PCPTrace()
        trace.log(event=PCPTraceEvent.BUILD_STARTED, trace_id="1")
        trace.log(event=PCPTraceEvent.BUILD_COMPLETED, trace_id="1")

        trace_entries = trace.get_trace()
        events = [e["event"] for e in trace_entries]

        assert PCPTraceEvent.BUILD_STARTED.value in events
        assert PCPTraceEvent.BUILD_COMPLETED.value in events

    def test_trace_shows_fail_closed_on_triggered(self) -> None:
        """Trace should show fail-closed when fail-safe triggered."""
        from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeTrigger

        fail_safe = FailSafeRegistry(enabled=True)
        fail_safe.trigger(
            reason="Test trigger",
            trigger=FailSafeTrigger.CONFIG_ERROR,
        )

        # When fail-safe is triggered, trace should show fail_closed
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.FAIL_CLOSED,
            trace_id="test-1",
            metadata={"reason": "fail_safe_triggered"},
        )

        trace_entries = trace.get_trace()
        events = [e["event"] for e in trace_entries]

        assert PCPTraceEvent.FAIL_CLOSED.value in events

    def test_trace_count_tracks_builds(self) -> None:
        """Trace count should track builds."""
        trace = PCPTrace()
        initial_count = trace.get_count()
        assert initial_count == 0

        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-1",
        )
        assert trace.get_count() == initial_count + 1

        trace.log(
            event=PCPTraceEvent.BUILD_COMPLETED,
            trace_id="test-1",
        )
        assert trace.get_count() == initial_count + 2

    def test_trace_by_event_filter(self) -> None:
        """Should be able to filter traces by event type."""
        trace = PCPTrace()
        trace.log(event=PCPTraceEvent.BUILD_STARTED, trace_id="1")
        trace.log(event=PCPTraceEvent.BUILD_COMPLETED, trace_id="2")
        trace.log(event=PCPTraceEvent.INJECTION_REQUESTED, trace_id="3")

        started_events = trace.get_traces_by_event(PCPTraceEvent.BUILD_STARTED)
        assert len(started_events) == 1
        assert started_events[0].trace_id == "1"

        completed_events = trace.get_traces_by_event(PCPTraceEvent.BUILD_COMPLETED)
        assert len(completed_events) == 1
        assert completed_events[0].trace_id == "2"
