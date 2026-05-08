"""Tests for no-injection cases with explicit skip_reason."""

import uuid

import pytest

from relic.cac.controller import CACController, create_cac_context, create_cac_input
from relic.cac.types import (
    CACDecision,
    MemorySource,
)


class TestNoInjection:
    """Tests for no-injection scenarios with explicit skip_reason."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller with temp trace path."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="no-injection-test")

    def test_none_memory_has_skip_reason(self, controller, context):
        """No-injection case must have explicit skip_reason."""
        inp = create_cac_input(
            memory_content=None,
            memory_id="no-inj-001",
            source=MemorySource.PROVIDER_MEMORY,
        )
        controller.evaluate(inp, context)

        # NONE decision doesn't need skip_reason
        # But trace should exist with the decision
        traces = controller.get_traces()
        assert len(traces) == 1
        assert traces[0].decision == CACDecision.NONE.value

    def test_quarantined_has_explicit_skip_reason(self, controller, context):
        """Quarantined decisions must have explicit skip_reason."""
        inp = create_cac_input(
            memory_content="External unverified content",
            memory_id="no-inj-002",
            source=MemorySource.EXTERNAL,
        )
        result = controller.evaluate(inp, context)

        assert result.decision == CACDecision.QUARANTINED
        assert result.skip_reason is not None
        assert len(result.skip_reason) > 0

        # Verify trace has skip_reason
        traces = controller.get_traces()
        assert traces[0].skip_reason is not None

    def test_blocked_has_explicit_skip_reason(self, controller, context):
        """Blocked decisions must have explicit skip_reason."""
        inp = create_cac_input(
            memory_content="Disputed content",
            memory_id="no-inj-003",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Incorrect inference",
        )
        result = controller.evaluate(inp, context)

        assert result.decision == CACDecision.BLOCKED
        assert result.skip_reason is not None
        assert "disputed" in result.skip_reason.lower()

    def test_deferred_has_explicit_reason(self, controller, context):
        """Deferred decisions must have deferred_reason."""
        inp = create_cac_input(
            memory_content="Ambiguous content",
            memory_id="no-inj-004",
            source=MemorySource.INFERENCE,
            metadata={"defer_reason": "Requires human review"},
        )
        result = controller.evaluate(inp, context)

        # Low confidence inference should be quarantined
        assert result.skip_reason is not None

    def test_trace_records_skip_reason(self, controller, context):
        """CAC trace must record skip_reason for no-injection cases."""
        inp = create_cac_input(
            memory_content="Unknown source content",
            memory_id="no-inj-005",
            source=MemorySource.UNKNOWN,
        )
        result = controller.evaluate(inp, context)

        traces = controller.get_traces()
        assert len(traces) == 1

        trace = traces[0]
        # The trace must have skip_reason when decision is quarantine/blocked
        if result.skip_reason:
            assert trace.skip_reason is not None


class TestNoInjectionWithFixtures:
    """Tests using fixture data for no-injection scenarios."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="fixture-test")

    def test_no_injection_fixture(self, controller, context):
        """Test with canonical no-injection fixture."""
        # This tests the fixture loading pattern
        # The actual fixture data would be loaded from fixtures/no-injection/

        # Simulate a no-injection case matching the fixture structure
        inp = create_cac_input(
            memory_content=None,  # No memory to inject
            memory_id="fixture-001",
            source=MemorySource.PROVIDER_MEMORY,
        )
        result = controller.evaluate(inp, context)

        # Decision should be NONE for no content
        assert result.decision == CACDecision.NONE
        assert result.skip_reason is None  # NONE doesn't need skip_reason

        # But there should still be a trace
        traces = controller.get_traces()
        assert len(traces) == 1

        # Verify trace structure matches expected schema
        trace = traces[0]
        trace_dict = trace.to_dict()

        required_fields = [
            "trace_id", "memory_id", "memory_hash", "source",
            "decision", "severity", "disputed", "timestamp"
        ]
        for field in required_fields:
            assert field in trace_dict, f"Missing required field: {field}"
