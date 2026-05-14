"""Integration tests for CAC ContextPack adapter.

These tests verify end-to-end CAC → PromptContextPack integration.
CAC becomes the ONLY path by which memory candidates are admitted.
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
from relic.context_pack.adapters.cac import (
    CACContextPackAdapter,
    CACContextPackAdapterResult,
)
from relic.context_pack.builder import ContextPackBuilder, create_context_pack_from_cac
from relic.context_pack.types import (
    PromptContextPack,
    MemoryCandidate,
    BlockedItem,
    TaskType,
)


@pytest.fixture
def controller(tmp_path):
    """Create a CAC controller."""
    trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
    return CACController(trace_path=trace_path)


@pytest.fixture
def context():
    """Create a test context."""
    return create_cac_context(session_id="integration-test")


@pytest.fixture
def adapter():
    """Create a CAC ContextPack adapter."""
    return CACContextPackAdapter()


@pytest.fixture
def builder():
    """Create a context pack builder."""
    return ContextPackBuilder()


class TestCACAdapterIntegration:
    """Integration tests for CAC adapter end-to-end."""

    def test_full_cac_to_context_pack_flow(
        self, controller, context, adapter, builder
    ):
        """Test complete CAC → ContextPack flow."""
        # Create diverse CAC decisions
        decisions = [
            # Admitted: Factual correction
            create_cac_input(
                memory_content="The capital of France is Paris",
                memory_id="fact-001",
                source=MemorySource.USER_CORRECTION,
                metadata={"correction_type": "factual"},
            ),
            # Blocked: Disputed
            create_cac_input(
                memory_content="Secret info",
                memory_id="disputed-001",
                source=MemorySource.INFERENCE,
                disputed=True,
                dispute_reason="User objection",
            ),
            # Admitted: Verified provider
            create_cac_input(
                memory_content="User prefers dark mode",
                memory_id="pref-001",
                source=MemorySource.PROVIDER_MEMORY,
                metadata={"verified": True},
            ),
            # Blocked: S1 quarantine (unknown source)
            create_cac_input(
                memory_content="Unverified claim",
                memory_id="unknown-001",
                source=MemorySource.UNKNOWN,
            ),
        ]

        # Evaluate all through CAC
        cac_results = []
        for inp in decisions:
            result = controller.evaluate(inp, context)
            cac_results.append((inp, result))

        # Build context pack
        for inp, result in cac_results:
            builder.add_cac_decision(inp, result)

        context_pack = builder.build()

        # Verify: 2 admitted, 2 blocked
        assert len(context_pack.memory_candidates) == 2
        assert len(context_pack.blocked_items) == 2

        # Verify admitted IDs
        admitted_ids = [c.candidate_id for c in context_pack.memory_candidates]
        assert "fact-001" in admitted_ids
        assert "pref-001" in admitted_ids

        # Verify blocked IDs
        blocked_ids = [b.item_id for b in context_pack.blocked_items]
        assert "disputed-001" in blocked_ids
        assert "unknown-001" in blocked_ids

    def test_adapter_batch_produces_correct_result(
        self, controller, context, adapter
    ):
        """Test adapter.batch produces correct CACContextPackAdapterResult."""
        inputs = [
            create_cac_input(
                memory_content="Good memory",
                memory_id="batch-good-001",
                source=MemorySource.USER_CORRECTION,
                metadata={"correction_type": "factual"},
            ),
            create_cac_input(
                memory_content="Bad disputed",
                memory_id="batch-bad-001",
                source=MemorySource.INFERENCE,
                disputed=True,
            ),
        ]

        results = [controller.evaluate(inp, context) for inp in inputs]
        batch_result = adapter.adapt_batch(list(zip(inputs, results)))

        # Verify structure
        assert isinstance(batch_result, CACContextPackAdapterResult)
        assert isinstance(batch_result.candidates, list)
        assert isinstance(batch_result.blocked, list)
        assert isinstance(batch_result.metadata, dict)

        # Verify counts
        assert len(batch_result.candidates) == 1
        assert len(batch_result.blocked) == 1
        assert batch_result.metadata["total_processed"] == 2

    def test_create_context_pack_from_cac_helper(self, controller, context):
        """Test the convenience function create_context_pack_from_cac."""
        inputs = [
            create_cac_input(
                memory_content="Memory 1",
                memory_id="helper-001",
                source=MemorySource.USER_CORRECTION,
                metadata={"correction_type": "factual"},
            ),
        ]
        results = [controller.evaluate(inp, context) for inp in inputs]

        context_pack = create_context_pack_from_cac(list(zip(inputs, results)))

        assert isinstance(context_pack, PromptContextPack)
        assert len(context_pack.memory_candidates) == 1


class TestCACAdapterMemoryCandidate:
    """Tests for MemoryCandidate in adapter."""

    def test_adapter_creates_correct_candidate(self, controller, context, adapter):
        """Test adapter creates MemoryCandidate with correct fields."""
        inp = create_cac_input(
            memory_content="Test content",
            memory_id="candidate-001",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        result = controller.evaluate(inp, context)

        adapt_result = adapter.adapt(inp, result)

        assert len(adapt_result.candidates) == 1
        candidate = adapt_result.candidates[0]

        assert isinstance(candidate, MemoryCandidate)
        assert candidate.candidate_id == "candidate-001"
        assert candidate.summary == "Test content"
        assert candidate.timestamp is not None


class TestCACAdapterBlockedItem:
    """Tests for BlockedItem in adapter."""

    def test_adapter_creates_correct_blocked_item(self, controller, context, adapter):
        """Test adapter creates BlockedItem with correct fields."""
        inp = create_cac_input(
            memory_content="Disputed content",
            memory_id="blocked-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="User says incorrect",
        )
        result = controller.evaluate(inp, context)

        adapt_result = adapter.adapt(inp, result)

        assert len(adapt_result.blocked) == 1
        blocked = adapt_result.blocked[0]

        assert isinstance(blocked, BlockedItem)
        assert blocked.item_id == "blocked-001"
        assert "disputed" in blocked.reason.lower()


class TestContextPackBuilderWithAdapter:
    """Tests for ContextPackBuilder using the CAC adapter."""

    def test_builder_reset_clears_state(self, controller, context, builder):
        """Test builder.reset() clears all state."""
        inp = create_cac_input(
            memory_content="Content",
            memory_id="reset-001",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        result = controller.evaluate(inp, context)
        builder.add_cac_decision(inp, result)

        assert builder.admitted_count == 1

        builder.reset()

        assert builder.admitted_count == 0
        assert builder.blocked_count == 0

    def test_builder_chaining(self, controller, context):
        """Test builder method chaining."""
        builder = ContextPackBuilder()

        inp1 = create_cac_input(
            memory_content="Content 1",
            memory_id="chain-001",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        inp2 = create_cac_input(
            memory_content="Content 2",
            memory_id="chain-002",
            source=MemorySource.PROVIDER_MEMORY,
            metadata={"verified": True},
        )

        result1 = controller.evaluate(inp1, context)
        result2 = controller.evaluate(inp2, context)

        # Method chaining
        builder.add_cac_decision(inp1, result1).add_cac_decision(inp2, result2)

        context_pack = builder.build()
        assert len(context_pack.memory_candidates) == 2


class TestCACIsOnlyPath:
    """Tests verifying CAC is the ONLY path for memory admission."""

    def test_all_memory_goes_through_cac(self, controller, context):
        """All memories in context pack must have CAC decisions."""
        builder = ContextPackBuilder()

        # All memories added via add_cac_decision
        for i in range(5):
            inp = create_cac_input(
                memory_content=f"Content {i}",
                memory_id=f"mem-{i}",
                source=MemorySource.PROVIDER_MEMORY,
                metadata={"verified": True},
            )
            result = controller.evaluate(inp, context)
            builder.add_cac_decision(inp, result)

        context_pack = builder.build()

        # All memory candidates have decision info in metadata
        for candidate in context_pack.memory_candidates:
            assert "decision" in candidate.metadata
            assert "severity" in candidate.metadata

    def test_context_pack_task_type_setting(self, controller, context):
        """Context pack correctly sets task type."""
        builder = ContextPackBuilder(task_type=TaskType.TECHNICAL)
        
        inp = create_cac_input(
            memory_content="Memory content",
            memory_id="task-type-001",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        result = controller.evaluate(inp, context)
        builder.add_cac_decision(inp, result)

        context_pack = builder.build()
        assert context_pack.task_type == TaskType.TECHNICAL
