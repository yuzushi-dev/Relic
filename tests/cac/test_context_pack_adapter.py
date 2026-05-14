"""Tests for CAC ContextPack adapter - disputed hint blocking.

These tests verify that disputed hints NEVER enter runtime context
through the CAC ContextPack adapter.
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
from relic.context_pack.types import PromptContextPack


class TestDisputedHintBlockingInAdapter:
    """Tests that disputed hints are blocked by the CAC ContextPack adapter."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="disputed-adapter-test")

    @pytest.fixture
    def adapter(self):
        """Create a CAC ContextPack adapter."""
        return CACContextPackAdapter()

    @pytest.fixture
    def builder(self):
        """Create a context pack builder."""
        return ContextPackBuilder()

    def test_disputed_never_admitted_as_candidate(self, controller, context, adapter):
        """Disputed hints are NEVER admitted as memory candidates."""
        inp = create_cac_input(
            memory_content="Disputed content that should not appear",
            memory_id="disputed-adapter-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="User claims incorrect",
        )
        result = controller.evaluate(inp, context)

        # Verify S0 severity
        assert result.severity == SeverityClass.S0
        assert result.decision == CACDecision.BLOCKED

        # Adapter must NOT create a candidate
        adapt_result = adapter.adapt(inp, result)

        assert len(adapt_result.candidates) == 0
        assert len(adapt_result.blocked) == 1
        assert "disputed" in adapt_result.blocked[0].reason.lower()

    def test_disputed_not_in_context_pack(self, controller, context, builder):
        """Disputed hints do NOT appear in PromptContextPack."""
        inp = create_cac_input(
            memory_content="Secret data that must never render",
            memory_id="disputed-context-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Privacy violation",
        )
        result = controller.evaluate(inp, context)

        # Add to context pack
        builder.add_cac_decision(inp, result)
        context_pack = builder.build()

        # Memory ID must NOT be in memory candidates
        admitted_ids = [c.candidate_id for c in context_pack.memory_candidates]
        assert "disputed-context-001" not in admitted_ids

        # Memory ID MUST be in blocked items
        blocked_ids = [b.item_id for b in context_pack.blocked_items]
        assert "disputed-context-001" in blocked_ids

    def test_disputed_across_all_sources_blocked(self, controller, context, builder):
        """Disputed flag blocks regardless of source."""
        sources = [
            MemorySource.PROVIDER_MEMORY,
            MemorySource.USER_CORRECTION,
            MemorySource.INFERENCE,
            MemorySource.EXTERNAL,
            MemorySource.UNKNOWN,
        ]

        for source in sources:
            inp = create_cac_input(
                memory_content=f"Disputed {source.value} content",
                memory_id=f"disputed-src-{source.value}",
                source=source,
                disputed=True,
                dispute_reason="Always disputed",
            )
            result = controller.evaluate(inp, context)
            builder.add_cac_decision(inp, result)

        context_pack = builder.build()

        # No memories should be admitted
        assert len(context_pack.memory_candidates) == 0

        # All should be blocked
        assert len(context_pack.blocked_items) == 5
        for source in sources:
            blocked_ids = [b.item_id for b in context_pack.blocked_items]
            assert f"disputed-src-{source.value}" in blocked_ids

    def test_disputed_with_multiple_reasons_blocked(self, controller, context, adapter):
        """Disputed hints with multiple reasons are still blocked."""
        inp = create_cac_input(
            memory_content="Content with multiple issues",
            memory_id="disputed-multi-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Multiple disputes: incorrect date, wrong person",
        )
        result = controller.evaluate(inp, context)

        adapt_result = adapter.adapt(inp, result)

        assert len(adapt_result.candidates) == 0
        assert len(adapt_result.blocked) == 1

    def test_disputed_content_never_appears_in_context(
        self, controller, context, builder
    ):
        """Verify disputed content never appears in context pack content."""
        secret_content = "SECRET_PASSWORD_12345"
        inp = create_cac_input(
            memory_content=secret_content,
            memory_id="disputed-secret-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Security concern",
        )
        result = controller.evaluate(inp, context)

        builder.add_cac_decision(inp, result)
        context_pack = builder.build()

        # Check all memory candidates - none should have secret content
        for candidate in context_pack.memory_candidates:
            assert secret_content not in candidate.summary


class TestDisputedHintInBatchProcessing:
    """Tests for disputed hints in batch processing."""

    @pytest.fixture
    def adapter(self):
        """Create a CAC ContextPack adapter."""
        return CACContextPackAdapter()

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="batch-test")

    def test_batch_with_disputed_and_non_disputed(
        self, controller, context, adapter
    ):
        """Batch processing correctly separates disputed from non-disputed."""
        # Non-disputed: should be admitted
        inp_good = create_cac_input(
            memory_content="Good factual memory",
            memory_id="good-001",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        result_good = controller.evaluate(inp_good, context)

        # Disputed: should be blocked
        inp_bad = create_cac_input(
            memory_content="Bad disputed memory",
            memory_id="disputed-batch-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="User objection",
        )
        result_bad = controller.evaluate(inp_bad, context)

        # Process batch
        batch_result = adapter.adapt_batch([
            (inp_good, result_good),
            (inp_bad, result_bad),
        ])

        # Should have one candidate and one blocked
        assert len(batch_result.candidates) == 1
        assert batch_result.candidates[0].candidate_id == "good-001"

        assert len(batch_result.blocked) == 1
        assert batch_result.blocked[0].item_id == "disputed-batch-001"

        # Metadata should reflect correct counts
        assert batch_result.metadata["admitted_count"] == 1
        assert batch_result.metadata["blocked_count"] == 1

    def test_batch_all_disputed_all_blocked(self, controller, context, adapter):
        """Batch with all disputed memories all blocked."""
        decisions = []
        for i in range(3):
            inp = create_cac_input(
                memory_content=f"Disputed content {i}",
                memory_id=f"disputed-batch-{i}",
                source=MemorySource.INFERENCE,
                disputed=True,
                dispute_reason=f"Objection {i}",
            )
            result = controller.evaluate(inp, context)
            decisions.append((inp, result))

        batch_result = adapter.adapt_batch(decisions)

        assert len(batch_result.candidates) == 0
        assert len(batch_result.blocked) == 3
        assert batch_result.metadata["admitted_count"] == 0
        assert batch_result.metadata["blocked_count"] == 3


class TestDisputedHintVsOtherBlockReasons:
    """Tests comparing disputed vs other block reasons."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="block-reasons")

    @pytest.fixture
    def builder(self):
        """Create a context pack builder."""
        return ContextPackBuilder()

    def test_disputed_blocks_with_s0_severity(
        self, controller, context, builder
    ):
        """Disputed memory gets S0 severity and is blocked."""
        inp = create_cac_input(
            memory_content="Disputed content",
            memory_id="disputed-s0-001",
            source=MemorySource.INFERENCE,
            disputed=True,
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S0
        assert result.decision == CACDecision.BLOCKED

        builder.add_cac_decision(inp, result)
        context_pack = builder.build()

        admitted_ids = [c.candidate_id for c in context_pack.memory_candidates]
        blocked_ids = [b.item_id for b in context_pack.blocked_items]
        
        assert "disputed-s0-001" not in admitted_ids
        assert "disputed-s0-001" in blocked_ids

    def test_s1_quarantine_blocks_without_disputed_flag(
        self, controller, context, builder
    ):
        """S1 quarantine blocks even without disputed flag."""
        inp = create_cac_input(
            memory_content="Unknown source content",
            memory_id="s1-no-dispute-001",
            source=MemorySource.UNKNOWN,
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S1
        assert result.decision == CACDecision.QUARANTINED

        builder.add_cac_decision(inp, result)
        context_pack = builder.build()

        admitted_ids = [c.candidate_id for c in context_pack.memory_candidates]
        blocked_ids = [b.item_id for b in context_pack.blocked_items]
        
        assert "s1-no-dispute-001" not in admitted_ids
        assert "s1-no-dispute-001" in blocked_ids

    def test_both_disputed_and_s1_have_zero_influence(
        self, controller, context, builder
    ):
        """Both disputed and S1 have zero runtime influence."""
        # Disputed
        inp_disputed = create_cac_input(
            memory_content="Disputed content",
            memory_id="disputed-zero-001",
            source=MemorySource.INFERENCE,
            disputed=True,
        )
        result_disputed = controller.evaluate(inp_disputed, context)

        # S1
        inp_s1 = create_cac_input(
            memory_content="S1 content",
            memory_id="s1-zero-001",
            source=MemorySource.UNKNOWN,
        )
        result_s1 = controller.evaluate(inp_s1, context)

        # Both blocked
        builder.add_cac_decision(inp_disputed, result_disputed)
        builder.add_cac_decision(inp_s1, result_s1)
        context_pack = builder.build()

        assert len(context_pack.memory_candidates) == 0
        assert len(context_pack.blocked_items) == 2
