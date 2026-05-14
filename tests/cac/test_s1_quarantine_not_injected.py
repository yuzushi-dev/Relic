"""Tests for S1 quarantine NOT being injected into runtime context.

These tests verify that S1 quarantined memories have ZERO runtime
influence - they must never appear in PromptContextPack.
"""

from __future__ import annotations

import uuid

import pytest

from relic.cac.controller import CACController, create_cac_context, create_cac_input
from relic.cac.types import (
    CACDecision,
    MemorySource,
    SeverityClass,
)
from relic.context_pack.adapters.cac import CACContextPackAdapter
from relic.context_pack.builder import ContextPackBuilder
from relic.context_pack.types import MemoryCandidate, BlockedItem


class TestS1QuarantineNotInjected:
    """Tests that S1 quarantined memory NEVER enters runtime context."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller with temp trace path."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="s1-quarantine-test")

    @pytest.fixture
    def adapter(self):
        """Create a CAC context pack adapter."""
        return CACContextPackAdapter()

    @pytest.fixture
    def builder(self):
        """Create a context pack builder."""
        return ContextPackBuilder()

    def test_s1_quarantine_not_admitted_as_candidate(
        self, controller, context, adapter
    ):
        """S1 quarantined memory is NOT admitted as a memory candidate."""
        # Unknown source -> S1 quarantine
        inp = create_cac_input(
            memory_content="S1 quarantined content",
            memory_id="s1-quar-001",
            source=MemorySource.UNKNOWN,
        )
        result = controller.evaluate(inp, context)

        # Verify S1 severity and QUARANTINED decision
        assert result.severity == SeverityClass.S1
        assert result.decision == CACDecision.QUARANTINED

        # Adapter must NOT create a candidate
        adapt_result = adapter.adapt(inp, result)

        assert len(adapt_result.candidates) == 0
        assert len(adapt_result.blocked) == 1
        # Check blocked reason mentions quarantined
        assert adapt_result.blocked[0].item_id == "s1-quar-001"

    def test_s1_quarantine_not_in_context_pack(
        self, controller, context, builder
    ):
        """S1 quarantined memory does NOT appear in PromptContextPack."""
        # External source -> S1 quarantine
        inp = create_cac_input(
            memory_content="External unverified content",
            memory_id="s1-external-001",
            source=MemorySource.EXTERNAL,
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S1
        assert result.decision == CACDecision.QUARANTINED

        # Add to context pack builder
        builder.add_cac_decision(inp, result)
        context_pack = builder.build()

        # Memory ID must NOT be in memory candidates
        admitted_ids = [c.candidate_id for c in context_pack.memory_candidates]
        assert "s1-external-001" not in admitted_ids

        # Memory ID MUST be in blocked items
        blocked_ids = [b.item_id for b in context_pack.blocked_items]
        assert "s1-external-001" in blocked_ids

    def test_s1_quarantine_zero_runtime_influence(
        self, controller, context, adapter
    ):
        """S1 quarantined memory has zero runtime influence."""
        inp = create_cac_input(
            memory_content="Low confidence inference",
            memory_id="s1-lowconf-001",
            source=MemorySource.INFERENCE,
            metadata={"confidence": 0.5},  # Low confidence
        )
        result = controller.evaluate(inp, context)

        # Verify quarantine
        assert result.severity == SeverityClass.S1
        assert result.decision == CACDecision.QUARANTINED

        # Adapter must not admit
        adapt_result = adapter.adapt(inp, result)
        assert len(adapt_result.candidates) == 0
        assert adapt_result.metadata["admitted_count"] == 0

    def test_multiple_s1_memories_all_blocked(
        self, controller, context, builder
    ):
        """Multiple S1 quarantined memories are all blocked."""
        s1_memories = [
            ("s1-multi-001", MemorySource.UNKNOWN),
            ("s1-multi-002", MemorySource.EXTERNAL),
            ("s1-multi-003", MemorySource.INFERENCE),
        ]

        for memory_id, source in s1_memories:
            inp = create_cac_input(
                memory_content=f"Content for {memory_id}",
                memory_id=memory_id,
                source=source,
            )
            result = controller.evaluate(inp, context)
            builder.add_cac_decision(inp, result)

        context_pack = builder.build()

        # No memories should be admitted
        assert len(context_pack.memory_candidates) == 0

        # All memories should be blocked
        assert len(context_pack.blocked_items) == 3


class TestS1QuarantineRenderEnforcement:
    """Tests that render enforces S1 quarantine."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="render-test")

    def test_render_blocks_s1_quarantine(self, controller, context):
        """Renderer blocks S1 quarantined memory from context pack."""
        inp = create_cac_input(
            memory_content="S1 content",
            memory_id="render-s1-001",
            source=MemorySource.UNKNOWN,
        )
        result = controller.evaluate(inp, context)

        # render_for_context_pack must return (False, None, metadata)
        allowed, content, metadata = controller.render_for_context_pack(inp, result)

        assert allowed is False
        assert content is None
        assert metadata.get("quarantined") is True
        assert metadata.get("zero_runtime_influence") is True

    def test_s1_with_quarantine_until_respected(self, controller, context):
        """S1 with quarantine_until is respected."""
        inp = create_cac_input(
            memory_content="Time-limited quarantine content",
            memory_id="quarantine-timed-001",
            source=MemorySource.EXTERNAL,
        )
        result = controller.evaluate(inp, context)

        # Should have quarantine time set
        assert result.quarantine_until is not None

        # Should be blocked
        allowed, _, metadata = controller.render_for_context_pack(inp, result)
        assert allowed is False
        assert metadata.get("quarantine_until") is not None


class TestS1VsOtherSeverities:
    """Tests comparing S1 vs other severity classes."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="severity-compare")

    @pytest.fixture
    def builder(self):
        """Create a context pack builder."""
        return ContextPackBuilder()

    def test_s0_blocked_s1_quarantined_none_admitted(
        self, controller, context, builder
    ):
        """S0 blocked, S1 quarantined, NONE admitted - different treatment."""
        # S0: Disputed (blocked)
        inp_s0 = create_cac_input(
            memory_content="Disputed content",
            memory_id="s0-blocked-001",
            source=MemorySource.INFERENCE,
            disputed=True,
        )
        result_s0 = controller.evaluate(inp_s0, context)

        # S1: Unknown source (quarantined)
        inp_s1 = create_cac_input(
            memory_content="Unknown source content",
            memory_id="s1-quar-001",
            source=MemorySource.UNKNOWN,
        )
        result_s1 = controller.evaluate(inp_s1, context)

        # NONE: Factual correction (admitted)
        inp_none = create_cac_input(
            memory_content="Fact: The sky is blue",
            memory_id="none-admit-001",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        result_none = controller.evaluate(inp_none, context)

        # Verify severities
        assert result_s0.severity == SeverityClass.S0
        assert result_s1.severity == SeverityClass.S1
        assert result_none.severity == SeverityClass.NONE

        # Add all to builder
        builder.add_cac_decision(inp_s0, result_s0)
        builder.add_cac_decision(inp_s1, result_s1)
        builder.add_cac_decision(inp_none, result_none)

        context_pack = builder.build()

        # Only NONE severity should be admitted
        assert len(context_pack.memory_candidates) == 1
        assert context_pack.memory_candidates[0].candidate_id == "none-admit-001"

        # S0 and S1 should be blocked
        assert len(context_pack.blocked_items) == 2
        blocked_ids = [b.item_id for b in context_pack.blocked_items]
        assert "s0-blocked-001" in blocked_ids
        assert "s1-quar-001" in blocked_ids

    def test_s2_admitted_with_warning(self, controller, context, builder):
        """S2 severity is admitted but may have warning."""
        inp = create_cac_input(
            memory_content="Provider memory with warning",
            memory_id="s2-warn-001",
            source=MemorySource.PROVIDER_MEMORY,
            metadata={"verified": True},
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S2

        builder.add_cac_decision(inp, result)
        context_pack = builder.build()

        # S2 should be admitted
        assert len(context_pack.memory_candidates) == 1
        assert context_pack.memory_candidates[0].candidate_id == "s2-warn-001"
