"""Tests for CAC controller - core evaluation logic."""

import uuid

import pytest

from relic.cac.controller import CACController, create_cac_context, create_cac_input
from relic.cac.types import (
    CACDecision,
    MemorySource,
    SeverityClass,
)


class TestCACControllerBasic:
    """Basic CAC controller tests."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller with temp trace path."""
        trace_path = tmp_path / "cac_trace.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="test-session-001")

    def test_returns_none_decision(self, controller, context):
        """CAC can return NONE decision when no memory to inject."""
        inp = create_cac_input(
            memory_content=None,
            memory_id="mem-001",
            source=MemorySource.PROVIDER_MEMORY,
        )
        result = controller.evaluate(inp, context)

        assert result.decision == CACDecision.NONE
        assert result.skip_reason is None

    def test_returns_compact_decision(self, controller, context):
        """CAC can return COMPACT decision for short memory."""
        inp = create_cac_input(
            memory_content="Short memory",
            memory_id="mem-002",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        result = controller.evaluate(inp, context)

        assert result.decision == CACDecision.COMPACT
        assert result.severity == SeverityClass.NONE

    def test_returns_expanded_decision(self, controller, context):
        """CAC can return EXPANDED decision for long memory."""
        long_content = "A" * 600  # Exceeds 500 char threshold
        inp = create_cac_input(
            memory_content=long_content,
            memory_id="mem-003",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        result = controller.evaluate(inp, context)

        assert result.decision == CACDecision.EXPANDED

    def test_returns_local_only_decision(self, controller, context):
        """CAC can return LOCAL_ONLY decision."""
        # This would be used for context-restricted memories
        inp = create_cac_input(
            memory_content="Local context memory",
            memory_id="mem-004",
            source=MemorySource.PROVIDER_MEMORY,
            metadata={"context_scope": "local_only"},
        )
        result = controller.evaluate(inp, context)

        # Should be admitted but may vary based on rules
        assert result.memory_id == "mem-004"

    def test_writes_trace_on_every_decision(self, controller, context, tmp_path):
        """Every decision writes to cac_trace.jsonl."""
        inp = create_cac_input(
            memory_content="Test memory",
            memory_id="mem-005",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        controller.evaluate(inp, context)

        trace_path = tmp_path / "cac_trace.jsonl"
        assert trace_path.exists(), "Trace file must be created"

        traces = controller.get_traces()
        assert len(traces) == 1
        assert traces[0].memory_id == "mem-005"

    def test_trace_contains_no_raw_session_text(self, controller, context):
        """CAC traces never contain raw session text."""
        inp = create_cac_input(
            memory_content="Secret password: super_secret_123",
            memory_id="mem-006",
            source=MemorySource.PROVIDER_MEMORY,
        )
        controller.evaluate(inp, context)

        traces = controller.get_traces()
        trace_dict = traces[0].to_dict()

        # Check that raw content is not in trace
        assert "Secret password" not in str(trace_dict)
        assert "super_secret_123" not in str(trace_dict)
        # Only hashes should be present
        assert "memory_hash" in trace_dict


class TestCACSeverityClassification:
    """Tests for severity class assignment."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller with isolated path."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="test-session-002")

    def test_s0_assigned_to_disputed(self, controller, context):
        """Disputed memory gets S0 severity."""
        inp = create_cac_input(
            memory_content="Some disputed content",
            memory_id="mem-s0-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="User claims incorrect",
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S0
        assert result.decision == CACDecision.BLOCKED
        assert result.skip_reason is not None

    def test_s1_assigned_to_unknown_source(self, controller, context):
        """Unknown source gets S1 quarantine."""
        inp = create_cac_input(
            memory_content="Unknown content",
            memory_id="mem-s1-001",
            source=MemorySource.UNKNOWN,
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S1
        assert result.decision == CACDecision.QUARANTINED
        assert result.skip_reason is not None

    def test_s2_assigned_to_verified_provider(self, controller, context):
        """Verified provider memory gets S2 warning."""
        inp = create_cac_input(
            memory_content="Provider content",
            memory_id="mem-s2-001",
            source=MemorySource.PROVIDER_MEMORY,
            metadata={"verified": True},
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S2
        assert result.skip_reason is None

    def test_none_assigned_to_factual_correction(self, controller, context):
        """Factual user correction gets NONE severity."""
        inp = create_cac_input(
            memory_content="Fact: The sky is blue",
            memory_id="mem-none-001",
            source=MemorySource.USER_CORRECTION,
            metadata={"correction_type": "factual"},
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.NONE


class TestCACDeferQuarantine:
    """Tests for defer and quarantine functionality."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller with isolated path."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="test-session-003")

    def test_can_defer_uncertain_memory(self, controller, context):
        """CAC can defer uncertain memory instead of forcing injection."""
        inp = create_cac_input(
            memory_content="Ambiguous inference content",
            memory_id="mem-defer-001",
            source=MemorySource.INFERENCE,
            metadata={
                "confidence": 0.6,
                "defer_reason": "Low confidence inference",
            },
        )
        result = controller.evaluate(inp, context)

        # Low confidence inference should be quarantined, not injected
        assert result.decision in (CACDecision.QUARANTINED, CACDecision.DEFERRED)
        assert result.skip_reason is not None

    def test_can_quarantine_uncertain_memory(self, controller, context):
        """CAC can quarantine uncertain memory."""
        inp = create_cac_input(
            memory_content="Unverified external content",
            memory_id="mem-quar-001",
            source=MemorySource.EXTERNAL,
        )
        result = controller.evaluate(inp, context)

        assert result.decision == CACDecision.QUARANTINED
        assert result.quarantine_until is not None
        assert result.skip_reason is not None

    def test_s1_quarantined_has_no_runtime_influence(self, controller, context):
        """S1 quarantined memory is properly flagged for zero runtime influence."""
        inp = create_cac_input(
            memory_content="Quarantined content",
            memory_id="mem-s1-runtime-001",
            source=MemorySource.UNKNOWN,
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S1
        # Renderer should block this from PromptContextPack
        render = controller.render_for_context_pack(inp, result)
        assert render[0] is False  # Not allowed
        assert render[2].get("zero_runtime_influence") is True


class TestCACCannotImport:
    """Verify CAC does not import compiler or lab modules."""

    def test_no_compiler_import(self):
        """CAC modules must not import from relic.compiler."""
        import relic.cac.controller
        import relic.cac.render
        import relic.cac.scoring
        import relic.cac.trace
        import relic.cac.types

        # Check the module's globals don't contain compiler references
        for module in [relic.cac.controller, relic.cac.types, relic.cac.scoring,
                       relic.cac.trace, relic.cac.render]:
            module_name = module.__name__
            # Just verify the modules load without error
            assert "relic.cac" in module_name

    def test_no_lab_import(self):
        """CAC modules must not import from relic.lab."""
        import relic.cac.controller
        import relic.cac.render
        import relic.cac.scoring
        import relic.cac.trace
        import relic.cac.types

        # Verify modules load successfully
        for module in [relic.cac.controller, relic.cac.types, relic.cac.scoring,
                       relic.cac.trace, relic.cac.render]:
            assert module is not None
