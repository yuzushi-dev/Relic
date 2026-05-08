"""Tests for disputed hint blocking - disputed hints NEVER render."""

import uuid

import pytest

from relic.cac.controller import CACController, create_cac_context, create_cac_input
from relic.cac.render import CACRenderer
from relic.cac.types import (
    CACDecision,
    MemorySource,
    SeverityClass,
)


class TestDisputedHintBlocking:
    """Tests that disputed hints are never rendered."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="disputed-test")

    def test_disputed_hint_blocked_at_s0(self, controller, context):
        """Disputed hints get S0 severity (hard block)."""
        inp = create_cac_input(
            memory_content="Disputed hint content",
            memory_id="disputed-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="User claims this is wrong",
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S0
        assert result.decision == CACDecision.BLOCKED
        assert result.skip_reason is not None

    def test_disputed_hint_never_renders(self, controller, context):
        """Disputed hints never render - even if content exists."""
        inp = create_cac_input(
            memory_content="This is disputed content that should never appear",
            memory_id="disputed-002",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Incorrect",
        )
        result = controller.evaluate(inp, context)

        # Get render result
        render = controller.render(inp, result)

        assert render.should_inject is False
        assert render.content is None
        assert "disputed" in render.metadata.get("blocked_reason", "")

    def test_disputed_hint_blocked_in_context_pack(self, controller, context):
        """Disputed hints have zero runtime influence via PromptContextPack."""
        inp = create_cac_input(
            memory_content="Disputed provider inference",
            memory_id="disputed-003",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Confidence too low",
        )
        result = controller.evaluate(inp, context)

        # Context pack integration
        allowed, content, metadata = controller.render_for_context_pack(inp, result)

        assert allowed is False
        assert content is None
        assert metadata.get("blocked_reason") == "disputed"

    def test_disputed_with_any_source_is_blocked(self, controller, context):
        """Disputed flag overrides source - always blocked regardless of source."""
        sources = [
            MemorySource.PROVIDER_MEMORY,
            MemorySource.USER_CORRECTION,
            MemorySource.INFERENCE,
            MemorySource.EXTERNAL,
        ]

        for source in sources:
            inp = create_cac_input(
                memory_content=f"Content from {source.value}",
                memory_id=f"disputed-src-{source.value}",
                source=source,
                disputed=True,
                dispute_reason="Always disputed",
            )
            result = controller.evaluate(inp, context)

            assert result.severity == SeverityClass.S0, f"S0 expected for {source}"
            assert result.decision == CACDecision.BLOCKED, f"BLOCKED expected for {source}"

    def test_disputed_with_multiple_reasons_blocked(self, controller, context):
        """Disputed hints with multiple dispute reasons are still blocked."""
        inp = create_cac_input(
            memory_content="Content with multiple issues",
            memory_id="disputed-multi-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Multiple disputes: incorrect date, wrong person",
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S0
        assert result.skip_reason is not None
        assert "disputed" in result.skip_reason.lower()

    def test_trace_for_disputed_hint(self, controller, context):
        """Trace correctly records disputed hint block."""
        inp = create_cac_input(
            memory_content="Disputed memory",
            memory_id="disputed-trace-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="User objection",
        )
        controller.evaluate(inp, context)

        traces = controller.get_traces()
        assert len(traces) == 1

        trace = traces[0]
        assert trace.disputed is True
        assert trace.decision == CACDecision.BLOCKED.value
        assert trace.severity == SeverityClass.S0.value
        assert trace.skip_reason is not None

        # Verify raw content not in trace
        trace_dict = trace.to_dict()
        assert "Disputed memory" not in str(trace_dict)


class TestDisputedHintRenderVerification:
    """Direct tests on the renderer to verify disputed blocking."""

    @pytest.fixture
    def renderer(self):
        """Create a CAC renderer."""
        return CACRenderer()

    def test_renderer_blocks_disputed_directly(self, renderer):
        """Renderer blocks disputed hints even without full controller."""
        from relic.cac.types import CACDecisionResult, CACInput, SeverityClass

        inp = CACInput(
            memory_content="Secret data that should not render",
            memory_hash="abc123",
            memory_id="render-disputed-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Testing renderer block",
        )

        result = CACDecisionResult(
            decision=CACDecision.BLOCKED,
            severity=SeverityClass.S0,
            memory_id="render-disputed-001",
            memory_hash="abc123",
            skip_reason="disputed_memory",
        )

        render = renderer.render(inp, result)

        assert render.should_inject is False
        assert render.content is None
        assert "disputed" in render.warning_message.lower()

    def test_renderer_allows_non_disputed(self, renderer):
        """Renderer allows non-disputed content with NONE severity."""
        from relic.cac.types import CACDecisionResult, CACInput, SeverityClass

        inp = CACInput(
            memory_content="Normal memory content",
            memory_hash="def456",
            memory_id="render-allowed-001",
            source=MemorySource.USER_CORRECTION,
            disputed=False,
            metadata={"correction_type": "factual"},
        )

        result = CACDecisionResult(
            decision=CACDecision.COMPACT,
            severity=SeverityClass.NONE,
            memory_id="render-allowed-001",
            memory_hash="def456",
        )

        render = renderer.render(inp, result)

        assert render.should_inject is True
        assert render.content is not None
