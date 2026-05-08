"""Tests for sensitive hint routing - S1 quarantine and severity routing."""

import uuid
from datetime import datetime, timedelta

import pytest

from relic.cac.controller import CACController, create_cac_context, create_cac_input
from relic.cac.types import (
    CACDecision,
    MemorySource,
    SeverityClass,
)


class TestSensitiveHintRouting:
    """Tests for routing sensitive hints based on severity class."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="sensitive-routing-test")

    def test_s1_routed_to_quarantine(self, controller, context):
        """S1 memories are routed to quarantine."""
        inp = create_cac_input(
            memory_content="Unknown source content",
            memory_id="s1-001",
            source=MemorySource.UNKNOWN,
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S1
        assert result.decision == CACDecision.QUARANTINED
        assert result.skip_reason is not None
        assert result.quarantine_until is not None

    def test_s2_routed_with_warning(self, controller, context):
        """S2 memories are admitted with warning."""
        inp = create_cac_input(
            memory_content="Verified provider content",
            memory_id="s2-001",
            source=MemorySource.PROVIDER_MEMORY,
            metadata={"verified": True},
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S2
        assert result.warning_message is not None

    def test_s0_routed_to_hard_block(self, controller, context):
        """S0 memories are hard blocked."""
        inp = create_cac_input(
            memory_content="Malicious content",
            memory_id="s0-001",
            source=MemorySource.INFERENCE,
            disputed=True,
            dispute_reason="Malicious",
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S0
        assert result.decision == CACDecision.BLOCKED

    def test_s1_quarantined_zero_runtime_influence(self, controller, context):
        """S1 quarantined memory has zero runtime influence."""
        inp = create_cac_input(
            memory_content="Quarantined external content",
            memory_id="s1-runtime-001",
            source=MemorySource.EXTERNAL,
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S1

        # Verify zero runtime influence via context pack
        allowed, content, metadata = controller.render_for_context_pack(inp, result)

        assert allowed is False
        assert content is None
        assert metadata.get("zero_runtime_influence") is True
        assert metadata.get("quarantined") is True

    def test_inference_low_confidence_routed_to_quarantine(self, controller, context):
        """Low confidence inference is routed to quarantine."""
        inp = create_cac_input(
            memory_content="Low confidence inference",
            memory_id="inf-low-001",
            source=MemorySource.INFERENCE,
            metadata={"confidence": 0.5},
        )
        result = controller.evaluate(inp, context)

        # Low confidence inference -> S1 quarantine
        assert result.severity == SeverityClass.S1
        assert result.decision == CACDecision.QUARANTINED

    def test_inference_high_confidence_routed_with_warning(self, controller, context):
        """High confidence inference is admitted with S2 warning."""
        inp = create_cac_input(
            memory_content="High confidence inference",
            memory_id="inf-high-001",
            source=MemorySource.INFERENCE,
            metadata={"confidence": 0.85},
        )
        result = controller.evaluate(inp, context)

        # High confidence inference -> S2 warning
        assert result.severity == SeverityClass.S2
        assert result.warning_message is not None

    def test_unverified_provider_memory_quarantined(self, controller, context):
        """Unverified provider memory is quarantined."""
        inp = create_cac_input(
            memory_content="Unverified provider memory",
            memory_id="prov-unv-001",
            source=MemorySource.PROVIDER_MEMORY,
            metadata={"verified": False},
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S1
        assert result.decision == CACDecision.QUARANTINED

    def test_verified_provider_memory_accepted_with_warning(self, controller, context):
        """Verified provider memory is accepted with S2 warning."""
        inp = create_cac_input(
            memory_content="Verified provider memory",
            memory_id="prov-v-001",
            source=MemorySource.PROVIDER_MEMORY,
            metadata={"verified": True},
        )
        result = controller.evaluate(inp, context)

        assert result.severity == SeverityClass.S2

    def test_all_severity_classes_assigned(self, controller, context):
        """All four severity classes (S0, S1, S2, NONE) are assigned."""
        cases = [
            # (source, disputed, metadata, expected_severity)
            (MemorySource.INFERENCE, True, {}, SeverityClass.S0),
            (MemorySource.UNKNOWN, False, {}, SeverityClass.S1),
            (MemorySource.PROVIDER_MEMORY, False, {"verified": True}, SeverityClass.S2),
            (MemorySource.USER_CORRECTION, False, {"correction_type": "factual"}, SeverityClass.NONE),
        ]

        for i, (source, disputed, metadata, expected) in enumerate(cases):
            inp = create_cac_input(
                memory_content=f"Memory {i}",
                memory_id=f"sev-{expected.value}-{i}",
                source=source,
                disputed=disputed,
                metadata=metadata,
            )
            result = controller.evaluate(inp, context)

            assert result.severity == expected, f"Expected {expected} for case {i}"


class TestQuarantineExpiration:
    """Tests for quarantine expiration logic."""

    @pytest.fixture
    def controller(self, tmp_path):
        """Create a CAC controller with isolated path."""
        trace_path = tmp_path / f"cac_trace_{uuid.uuid4().hex[:8]}.jsonl"
        return CACController(trace_path=trace_path)

    @pytest.fixture
    def context(self):
        """Create a test context."""
        return create_cac_context(session_id="quarantine-test")

    def test_quarantine_has_default_expiration(self, controller, context):
        """Quarantined memories have a default expiration time."""
        inp = create_cac_input(
            memory_content="Quarantined content",
            memory_id="quar-exp-001",
            source=MemorySource.EXTERNAL,
        )
        result = controller.evaluate(inp, context)

        assert result.quarantine_until is not None
        assert result.quarantine_until > datetime.utcnow()

        # Default is 24 hours
        expected_min = datetime.utcnow() + timedelta(hours=23)
        expected_max = datetime.utcnow() + timedelta(hours=25)
        assert expected_min < result.quarantine_until < expected_max

    def test_quarantine_metadata_recorded(self, controller, context):
        """Quarantine state is recorded in trace metadata."""
        inp = create_cac_input(
            memory_content="Quarantined content",
            memory_id="quar-meta-001",
            source=MemorySource.UNKNOWN,
        )
        controller.evaluate(inp, context)

        traces = controller.get_traces()
        assert len(traces) == 1

        # Trace should have quarantine-related info
        trace = traces[0]
        assert trace.skip_reason is not None
        assert "unknown_source" in trace.skip_reason.lower()
