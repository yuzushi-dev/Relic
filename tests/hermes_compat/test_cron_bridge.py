"""
Tests for CronBridge and RuntimeDecisionResult.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from relic.hermes_runtime import RuntimeDecision, RuntimeDecisionReason
from relic.hermes_adapter.cron_bridge import (
    RuntimeDecisionResult,
    CronBridge,
    get_bridge,
    evaluate_proactive_delivery,
)


class TestRuntimeDecisionResult:
    """Tests for RuntimeDecisionResult dataclass."""

    def test_create_no_reply_result(self):
        """Test creating NO_REPLY result."""
        result = RuntimeDecisionResult(
            decision=RuntimeDecision.NO_REPLY,
            reason_codes=[RuntimeDecisionReason.no_due_work],
            subject_ref="subject-123",
        )
        assert result.decision == RuntimeDecision.NO_REPLY
        assert result.candidate_message is None
        assert not result.is_deliverable()

    def test_create_candidate_result(self):
        """Test creating CANDIDATE result."""
        result = RuntimeDecisionResult(
            decision=RuntimeDecision.CANDIDATE,
            reason_codes=[],
            subject_ref="subject-456",
            candidate_message="Hello, how are you?",
        )
        assert result.decision == RuntimeDecision.CANDIDATE
        assert result.candidate_message == "Hello, how are you?"
        assert result.candidate_message_hash is not None
        assert result.candidate_message_hash.startswith("sha256:")
        assert result.is_deliverable()

    def test_create_deliver_result(self):
        """Test creating DELIVER result."""
        result = RuntimeDecisionResult(
            decision=RuntimeDecision.DELIVER,
            reason_codes=[],
            subject_ref="subject-789",
            candidate_message="Good morning!",
            media_type="voice",
        )
        assert result.decision == RuntimeDecision.DELIVER
        assert result.media_type == "voice"
        assert result.is_deliverable()

    def test_auto_compute_message_hash(self):
        """Test that message hash is auto-computed."""
        result = RuntimeDecisionResult(
            decision=RuntimeDecision.CANDIDATE,
            reason_codes=[],
            subject_ref="subject-000",
            candidate_message="test message",
        )
        assert result.candidate_message_hash is not None
        assert result.candidate_message_hash.startswith("sha256:")

    def test_preserve_explicit_hash(self):
        """Test that explicit hash is preserved."""
        explicit_hash = "sha256:customhash123"
        result = RuntimeDecisionResult(
            decision=RuntimeDecision.CANDIDATE,
            reason_codes=[],
            subject_ref="subject-001",
            candidate_message="test",
            candidate_message_hash=explicit_hash,
        )
        assert result.candidate_message_hash == explicit_hash

    def test_to_dict(self):
        """Test result serialization."""
        result = RuntimeDecisionResult(
            decision=RuntimeDecision.CANDIDATE,
            reason_codes=[RuntimeDecisionReason.followup_expired],
            subject_ref="subject-dict",
            candidate_message="test",
            media_type="text",
        )
        data = result.to_dict()
        assert data["decision"] == "CANDIDATE"
        assert data["subject_ref"] == "subject-dict"
        assert data["media_type"] == "text"
        assert "decided_at" in data

    def test_from_dict(self):
        """Test result deserialization."""
        data = {
            "decision": "DELIVER",
            "reason_codes": [],
            "subject_ref": "subject-from-dict",
            "candidate_message": "hello",
            "media_type": "text",
            "decided_at": "2026-05-16T12:00:00+00:00",
        }
        result = RuntimeDecisionResult.from_dict(data)
        assert result.decision == RuntimeDecision.DELIVER
        assert result.subject_ref == "subject-from-dict"
        assert result.candidate_message == "hello"

    def test_with_trace_event_id(self):
        """Test adding trace event ID."""
        result = RuntimeDecisionResult(
            decision=RuntimeDecision.CANDIDATE,
            reason_codes=[],
            subject_ref="subject-trace",
        )
        trace_id = uuid4()
        updated = result.with_trace_event_id(trace_id)
        assert result.trace_event_id is None
        assert updated.trace_event_id == trace_id
        assert updated.subject_ref == "subject-trace"  # Immutable

    def test_is_deliverable(self):
        """Test deliverability check."""
        no_reply = RuntimeDecisionResult(
            decision=RuntimeDecision.NO_REPLY,
            reason_codes=[],
            subject_ref="s1",
        )
        blocked = RuntimeDecisionResult(
            decision=RuntimeDecision.BLOCKED,
            reason_codes=[],
            subject_ref="s2",
        )
        candidate = RuntimeDecisionResult(
            decision=RuntimeDecision.CANDIDATE,
            reason_codes=[],
            subject_ref="s3",
        )
        deliver = RuntimeDecisionResult(
            decision=RuntimeDecision.DELIVER,
            reason_codes=[],
            subject_ref="s4",
        )
        assert not no_reply.is_deliverable()
        assert not blocked.is_deliverable()
        assert candidate.is_deliverable()
        assert deliver.is_deliverable()

    def test_result_is_frozen(self):
        """Test that result is immutable."""
        result = RuntimeDecisionResult(
            decision=RuntimeDecision.NO_REPLY,
            reason_codes=[],
            subject_ref="subject-frozen",
        )
        with pytest.raises(Exception):  # frozen dataclass
            result.decision = RuntimeDecision.DELIVER


class TestCronBridge:
    """Tests for CronBridge."""

    def test_create_bridge(self):
        """Test creating CronBridge."""
        bridge = CronBridge(
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        assert bridge.gumi_instance_id == "gumi-main"
        assert bridge.hermes_profile_id == "profile-default"

    def test_evaluate_no_message(self):
        """Test evaluation with no candidate message."""
        bridge = CronBridge()
        result = bridge.evaluate_proactive_delivery(
            subject_ref="subject-123",
            candidate_message=None,
        )
        assert result.decision == RuntimeDecision.NO_REPLY
        assert RuntimeDecisionReason.no_due_work in result.reason_codes
        assert not result.is_deliverable()

    def test_evaluate_with_message(self):
        """Test evaluation with candidate message."""
        bridge = CronBridge()
        result = bridge.evaluate_proactive_delivery(
            subject_ref="subject-456",
            candidate_message="Hello!",
            media_type="voice",
        )
        assert result.decision == RuntimeDecision.CANDIDATE
        assert result.candidate_message == "Hello!"
        assert result.media_type == "voice"
        assert result.is_deliverable()

    def test_evaluate_quiet_hours(self):
        """Test quiet hours evaluation."""
        bridge = CronBridge()
        # Placeholder implementation returns False
        assert bridge.evaluate_quiet_hours("subject-123") is False

    def test_evaluate_platform_allowlist(self):
        """Test platform allowlist evaluation."""
        bridge = CronBridge()
        # Placeholder implementation returns True
        assert bridge.evaluate_platform_allowlist("subject-123", "telegram") is True

    def test_default_gumi_instance(self):
        """Test default gumi instance in result."""
        bridge = CronBridge()
        result = bridge.evaluate_proactive_delivery(
            subject_ref="subject-default",
            candidate_message="test",
        )
        assert result.gumi_instance_id == "default"
        assert result.hermes_profile_id == "default"

    def test_custom_gumi_instance(self):
        """Test custom gumi instance in result."""
        bridge = CronBridge(
            gumi_instance_id="gumi-custom",
            hermes_profile_id="profile-custom",
        )
        result = bridge.evaluate_proactive_delivery(
            subject_ref="subject-custom",
            candidate_message="test",
        )
        assert result.gumi_instance_id == "gumi-custom"
        assert result.hermes_profile_id == "profile-custom"


class TestCronBridgeConvenience:
    """Tests for convenience functions."""

    def test_get_bridge(self):
        """Test get_bridge returns singleton."""
        bridge1 = get_bridge()
        bridge2 = get_bridge()
        assert bridge1 is bridge2

    def test_evaluate_proactive_delivery(self):
        """Test convenience evaluate function."""
        result = evaluate_proactive_delivery(
            subject_ref="subject-func",
            candidate_message="test message",
        )
        assert result.decision == RuntimeDecision.CANDIDATE
        assert result.subject_ref == "subject-func"


class TestCronWiringTimezoneConsistency:
    """FIX D: _subject_now and _last_outbound_datetime must both return tz-aware datetimes."""

    def test_subject_now_is_tz_aware_without_profile(self):
        from relic.gumi_plugin.cron_wiring import _subject_now
        now = _subject_now("nonexistent_subject_tz_test")
        assert now.tzinfo is not None, "_subject_now must return tz-aware datetime"

    def test_last_outbound_datetime_is_tz_aware(self, tmp_path):
        from relic.gumi_plugin.cron_wiring import _last_outbound_datetime
        # Create a MEMORY.md so the function has something to stat
        (tmp_path / "MEMORY.md").write_text("x")
        last_dt = _last_outbound_datetime(tmp_path, "nonexistent_subject_tz_test")
        assert last_dt is not None
        assert last_dt.tzinfo is not None, "_last_outbound_datetime must return tz-aware datetime"
