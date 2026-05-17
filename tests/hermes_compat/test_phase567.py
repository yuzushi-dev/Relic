"""
Tests for Phase 5, 6, 7 modules.
"""

import pytest
from datetime import datetime, timezone, timedelta

from relic.hermes_adapter.handoff_gate import (
    HandoffGate,
    HandoffRequest,
    HandoffDecision,
    HandoffDecisionValue,
    HandoffRisk,
    get_handoff_gate,
    evaluate_handoff,
)
from relic.hermes_adapter.approvals import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalResolution,
    ApprovalType,
    ApprovalDecision,
    RiskLevel,
    get_approval_manager,
    request_approval,
    resolve_approval,
)
from relic.hermes_adapter.observability import (
    ObservabilityBridge,
    RedactedSpan,
    RedactionLevel,
    get_observability_bridge,
)
from relic.hermes_adapter.prompt_cache import (
    PromptCachePolicy,
    CacheKey,
    CacheInvalidation,
    CacheSection,
    CacheInvalidationReason,
    get_cache_policy,
)
from relic.hermes_adapter.source_policy import (
    SourcePolicy,
    SourceClass,
    SourceClassification,
    ConsentState,
    get_source_policy,
    classify_source,
    check_evidence_eligibility,
)
from relic.hermes_adapter.envelope import HermesRuntimeEnvelope


class TestHandoffGate:
    """Tests for HandoffGate."""

    def test_create_handoff_request(self):
        """Test creating handoff request."""
        request = HandoffRequest(
            source_session_id="session-123",
            source_profile_id="profile-a",
            target_profile_id="profile-b",
            reason="User requested model change",
        )
        assert request.source_session_id == "session-123"
        assert request.preserve_context is True

    def test_evaluate_handoff_authorized(self):
        """Test handoff evaluation with authorization."""
        gate = HandoffGate(emit_events=False)
        request = HandoffRequest(
            source_session_id="session-123",
            source_profile_id="profile-a",
            target_profile_id="profile-b",
        )
        result = gate.evaluate(request, "subject-123")
        assert result.decision == HandoffDecisionValue.AUTHORIZED
        assert result.risk_level == HandoffRisk.LOW

    def test_evaluate_handoff_safety_review_blocked(self):
        """Test handoff evaluation."""
        gate = HandoffGate(emit_events=False)
        request = HandoffRequest(
            source_session_id="session-123",
            source_profile_id="profile-a",
            target_profile_id="profile-b",
        )
        result = gate.evaluate(request, "subject-123")
        assert result.decision == HandoffDecisionValue.AUTHORIZED

    def test_handoff_decision_to_dict(self):
        """Test handoff decision serialization."""
        decision = HandoffDecision(
            handoff_id="handoff-123",
            decision=HandoffDecisionValue.AUTHORIZED,
            risk_level=HandoffRisk.LOW,
            reason_codes=[],
            subject_ref="subject-123",
        )
        data = decision.to_dict()
        assert data["handoff_id"] == "handoff-123"
        assert data["decision"] == "AUTHORIZED"

    def test_convenience_functions(self):
        """Test convenience functions."""
        gate1 = get_handoff_gate()
        gate2 = get_handoff_gate()
        assert gate1 is gate2

        # Use emit_events=False gate for testing
        gate = HandoffGate(emit_events=False)
        request = HandoffRequest(
            source_session_id="session-456",
            source_profile_id="profile-a",
            target_profile_id="profile-b",
        )
        result = gate.evaluate(request, "subject-456")
        assert isinstance(result, HandoffDecision)


class TestApprovals:
    """Tests for ApprovalManager."""

    def test_create_approval_request(self):
        """Test creating approval request."""
        request = ApprovalRequest.create(
            approval_type=ApprovalType.DELIVERY,
            action_description="Deliver proactive message",
            risk_level=RiskLevel.MEDIUM,
            subject_ref="subject-123",
        )
        assert request.approval_type == ApprovalType.DELIVERY
        assert request.risk_level == RiskLevel.MEDIUM

    def test_approval_lifecycle(self):
        """Test approval request and resolution."""
        manager = ApprovalManager(emit_events=False)

        request = ApprovalRequest.create(
            approval_type=ApprovalType.HANDOFF,
            action_description="Change model",
            risk_level=RiskLevel.LOW,
            subject_ref="subject-123",
        )
        manager.request(request)

        pending = manager.get_pending(request.approval_id)
        assert pending is not None

        resolution = ApprovalResolution(
            approval_id=request.approval_id,
            decision=ApprovalDecision.GRANTED,
            resolved_by="user",
        )
        manager.resolve(resolution)

        resolved = manager.get_resolved(request.approval_id)
        assert resolved is not None
        assert resolved.decision == ApprovalDecision.GRANTED

    def test_approval_request_to_dict(self):
        """Test approval request serialization."""
        request = ApprovalRequest.create(
            approval_type=ApprovalType.TOOL_EXECUTION,
            action_description="Run external tool",
            risk_level=RiskLevel.HIGH,
            subject_ref="subject-123",
        )
        data = request.to_dict()
        assert data["approval_type"] == "tool_execution"
        assert data["risk_level"] == "high"

    def test_convenience_functions(self):
        """Test convenience functions."""
        manager1 = get_approval_manager()
        manager2 = get_approval_manager()
        assert manager1 is manager2


class TestObservabilityBridge:
    """Tests for ObservabilityBridge."""

    def test_create_span(self):
        """Test creating redacted span."""
        bridge = ObservabilityBridge(export_enabled=False)
        span = bridge.create_span(
            trace_id="trace-123",
            name="model_call",
            attributes={"model": "gpt-4", "temperature": 0.7},
        )
        assert span.trace_id.startswith("sha256:")
        assert span.redaction_level == RedactionLevel.REDACTED

    def test_end_span(self):
        """Test ending span."""
        bridge = ObservabilityBridge()
        start = datetime.now(timezone.utc)
        span = bridge.create_span("trace-123", "test", start_time=start)
        ended = bridge.end_span(span, end_time=start + timedelta(seconds=1))
        assert ended.duration_ms is not None
        assert ended.duration_ms > 0

    def test_redact_attributes(self):
        """Test attribute redaction."""
        bridge = ObservabilityBridge()
        attrs = {
            "user_id": "sensitive",
            "subject_name": "sensitive",
            "model": "gpt-4",
            "temperature": 0.7,
        }
        redacted = bridge._redact_attributes(attrs)
        assert "user_id" not in redacted
        assert "subject_name" not in redacted
        assert "model" in redacted
        assert "temperature" in redacted

    def test_filter_metrics(self):
        """Test metrics filtering."""
        bridge = ObservabilityBridge()
        metrics = {
            "latency_ms": 100,
            "tokens": 50,
            "user_message": "sensitive",
        }
        filtered = bridge._filter_metrics(metrics)
        assert "latency_ms" in filtered
        assert "tokens" in filtered
        assert "user_message" not in filtered

    def test_export_disabled(self):
        """Test export is disabled by default."""
        bridge = ObservabilityBridge(export_enabled=False)
        span = bridge.create_span("trace-123", "test")
        assert bridge.export_span(span) is False

    def test_export_enabled(self):
        """Test export when enabled."""
        bridge = ObservabilityBridge(export_enabled=True)
        span = bridge.create_span("trace-123", "test")
        assert bridge.export_span(span) is True
        assert bridge.export_count == 1


class TestPromptCachePolicy:
    """Tests for PromptCachePolicy."""

    def test_create_cache_key(self):
        """Test creating cache key."""
        policy = get_cache_policy()
        key = policy.create_cache_key(
            subject_ref="subject-123",
            hermes_profile_id="profile-default",
            sections=[CacheSection.SYSTEM_INSTRUCTIONS, CacheSection.CONTEXT_PACK],
            policy_snapshot_hash="hash-abc",
            profile_version="v1.0",
        )
        assert key.subject_ref == "subject-123"
        assert key.policy_snapshot_hash == "hash-abc"

    def test_cache_key_validity(self):
        """Test cache key validity check."""
        policy = get_cache_policy()
        key = policy.create_cache_key(
            subject_ref="subject-123",
            hermes_profile_id="profile-default",
            sections=[CacheSection.SYSTEM_INSTRUCTIONS],
            policy_snapshot_hash="hash-abc",
            profile_version="v1.0",
        )
        assert key.is_valid() is True

    def test_cache_invalidation(self):
        """Test cache invalidation."""
        policy = get_cache_policy()
        policy.create_cache_key(
            subject_ref="subject-456",
            hermes_profile_id="profile-default",
            sections=[CacheSection.SYSTEM_INSTRUCTIONS],
            policy_snapshot_hash="hash-abc",
            profile_version="v1.0",
        )

        invalidation = policy.invalidate(
            subject_ref="subject-456",
            reason=CacheInvalidationReason.POLICY_CHANGED,
            old_policy_hash="hash-abc",
            new_policy_hash="hash-xyz",
        )
        assert invalidation.reason == CacheInvalidationReason.POLICY_CHANGED

    def test_is_cacheable(self):
        """Test cacheable section check."""
        policy = get_cache_policy()
        assert policy.is_cacheable(CacheSection.SYSTEM_INSTRUCTIONS) is True
        assert policy.is_cacheable(CacheSection.PROFILE_SUMMARY) is False

    def test_cache_key_includes_section(self):
        """Test cache key section check."""
        key = CacheKey(
            key_id="key-123",
            subject_ref="subject-123",
            hermes_profile_id="profile-default",
            sections=(CacheSection.SYSTEM_INSTRUCTIONS,),
            policy_snapshot_hash="hash",
            profile_version="v1",
        )
        assert key.includes_section(CacheSection.SYSTEM_INSTRUCTIONS) is True
        assert key.includes_section(CacheSection.CONTEXT_PACK) is False


class TestSourcePolicy:
    """Tests for SourcePolicy."""

    def test_classify_user_direct(self):
        """Test classifying user direct source."""
        policy = get_source_policy()
        envelope = HermesRuntimeEnvelope(
            sender_ref="sender-123",
            platform="telegram",
            subject_ref="subject-123",
        )
        classification = policy.classify(envelope)
        assert classification.source_class == SourceClass.USER_DIRECT
        assert classification.is_evidence_eligible is True

    def test_classify_tool_execution(self):
        """Test classifying tool execution result."""
        policy = get_source_policy()
        envelope = HermesRuntimeEnvelope(
            tool_call_id="tool-123",
            subject_ref="subject-123",
        )
        classification = policy.classify(envelope)
        assert classification.source_class == SourceClass.TOOL_EXECUTION_RESULT
        assert classification.is_evidence_eligible is True
        assert classification.provenance_required is True

    def test_classify_proactive_delivery(self):
        """Test classifying proactive delivery."""
        policy = get_source_policy()
        envelope = HermesRuntimeEnvelope(
            tool_call_id="proactive_checkin",
            subject_ref="subject-123",
        )
        classification = policy.classify(envelope)
        assert classification.source_class == SourceClass.PROACTIVE_DELIVERY
        assert classification.is_evidence_eligible is False

    def test_evidence_eligibility_with_consent(self):
        """Test evidence eligibility with consent."""
        assert check_evidence_eligibility(
            SourceClass.GUMI_DIEGETIC_EVENT,
            ConsentState.GRANTED,
        ) is False

        assert check_evidence_eligibility(
            SourceClass.USER_DIRECT,
            ConsentState.NOT_REQUIRED,
        ) is True

    def test_web_source_requires_explicit_request(self):
        """Test web source requires explicit request."""
        assert check_evidence_eligibility(
            SourceClass.PUBLIC_WEB_SOURCE,
            ConsentState.GRANTED,
            is_explicit_request=False,
        ) is False

        assert check_evidence_eligibility(
            SourceClass.PUBLIC_WEB_SOURCE,
            ConsentState.GRANTED,
            is_explicit_request=True,
        ) is True

    def test_convenience_functions(self):
        """Test convenience functions."""
        policy1 = get_source_policy()
        policy2 = get_source_policy()
        assert policy1 is policy2
