"""Tests for ResumeReconciliation."""

from datetime import datetime, timezone, timedelta

import pytest

from relic.hermes_runtime import (
    ReconciliationCheck,
    ReconciliationDecision,
    ReconciliationResult,
    ResumeReconciliation,
    SessionResumeState,
)


class TestResumeReconciliation:
    """Test ResumeReconciliation state machine."""

    def test_resume_reconciliation_allows_clean_state(self):
        """ALLOW when all checks pass (clean state)."""
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            session_key_hash="abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )
        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123", pending_output=None)

        assert result.decision == ReconciliationDecision.ALLOW
        assert result.failed_checks == []
        assert result.pending_output_held is False

    def test_resume_reconciliation_blocks_paused_continuity_scope(self):
        """REVIEW_REQUIRED when continuity scope is paused."""
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            session_key_hash="abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=True,  # paused
            followup_attempt_count=0,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )
        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123", pending_output=None)

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.CONTINUITY_SCOPE_PAUSE in result.failed_checks
        assert result.pending_output_held is False

    def test_resume_reconciliation_blocks_expired_marker(self):
        """REVIEW_REQUIRED when continuity marker TTL is expired."""
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            session_key_hash="abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # expired
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )
        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123", pending_output=None)

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.CONTINUITY_MARKER_TTL in result.failed_checks

    def test_resume_reconciliation_blocks_unknown_delivery_state(self):
        """REVIEW_REQUIRED when delivery state is unknown (manual review required)."""
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            session_key_hash="abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            output_sanitizer_clean=True,
            delivery_state_known=False,  # unknown
        )
        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123", pending_output=None)

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.DELIVERY_STATE_KNOWN in result.failed_checks

    def test_resume_reconciliation_holds_pending_output(self):
        """pending_output_held=True when reconciliation fails and output is present."""
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            session_key_hash="abc123",
            platform_allowlist_valid=False,  # fails check
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )
        reconciler = ResumeReconciliation(state)
        pending = {"content": "test output", "target_platform": "telegram"}
        result = reconciler.reconcile(session_key_hash="abc123", pending_output=pending)

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert result.pending_output_held is True
        assert ReconciliationCheck.PLATFORM_ALLOWLIST in result.failed_checks

    def test_resume_reconciliation_blocks_session_key_mismatch(self):
        """REVIEW_REQUIRED when session key hash does not match."""
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            session_key_hash="abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )
        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="wrong_hash", pending_output=None)

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.SESSION_KEY_HASH in result.failed_checks

    def test_resume_reconciliation_blocks_safety_review_required(self):
        """REVIEW_REQUIRED when safety review is required."""
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            session_key_hash="abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=True,  # requires review
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )
        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123", pending_output=None)

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.SAFETY_REVIEW_STATE in result.failed_checks

    def test_resume_reconciliation_blocks_output_sanitizer(self):
        """REVIEW_REQUIRED when output sanitizer blocks."""
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            session_key_hash="abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            output_sanitizer_clean=False,  # blocked
            delivery_state_known=True,
        )
        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123", pending_output=None)

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.OUTPUT_SANITIZER in result.failed_checks

    def test_resume_reconciliation_result_to_dict(self):
        """ReconciliationResult serializes correctly."""
        result = ReconciliationResult(
            decision=ReconciliationDecision.REVIEW_REQUIRED,
            failed_checks=[ReconciliationCheck.DELIVERY_STATE_KNOWN, ReconciliationCheck.PLATFORM_ALLOWLIST],
            pending_output_held=True,
            metadata={"note": "manual review required"},
        )
        d = result.to_dict()

        assert d["decision"] == "REVIEW_REQUIRED"
        assert d["failed_checks"] == ["delivery_state_known", "platform_allowlist"]
        assert d["pending_output_held"] is True
        assert d["metadata"]["note"] == "manual review required"
