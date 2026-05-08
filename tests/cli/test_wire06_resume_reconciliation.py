"""Tests for WIRE06: Resume reconciliation wiring.

These tests verify:
- Resume pending output enters reconciliation
- Resume with unknown delivery state triggers manual review
- Resume re-checks allowlist
- Resume re-checks TTL and pause conditions
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from relic.hermes_plugin import resume_hooks
from relic.hermes_runtime import (
    ReconciliationCheck,
    ReconciliationDecision,
    ResumeReconciliation,
    SessionResumeState,
)


class TestResumePendingOutputEntersReconciliation:
    """Test that resume pending output enters reconciliation."""

    def test_resume_pending_output_enters_reconciliation(self) -> None:
        """When Hermes resumes with pending output, reconciliation should be called."""
        # Build a valid session state (all checks pass)
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )

        pending_output = {"message": "test message", "target": "telegram"}

        # Run reconciliation
        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", pending_output)

        # With all valid state, should ALLOW
        assert result.decision == ReconciliationDecision.ALLOW
        assert len(result.failed_checks) == 0
        assert result.pending_output_held is False

    def test_resume_rejects_when_platform_not_allowlisted(self) -> None:
        """Resume should be blocked when platform not allowlisted."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=False,  # Blocked
            delivery_enabled=True,
            continuity_marker_active=True,
            delivery_state_known=True,
        )

        pending_output = {"message": "test message", "target": "telegram"}

        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", pending_output)

        # Should be REVIEW_REQUIRED
        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.PLATFORM_ALLOWLIST in result.failed_checks
        # Pending output should be held
        assert result.pending_output_held is True

    def test_resume_with_failed_reconciliation_holds_output(self) -> None:
        """When reconciliation fails, pending output should be held."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=False,
            delivery_enabled=True,
            continuity_marker_active=True,
            delivery_state_known=True,
        )

        pending_output = {"message": "test message"}

        # Clear any existing holds
        resume_hooks.clear_pending_output_hold_store()

        # Run hook
        hook_result = resume_hooks.on_hermes_session_resume(
            session_key_hash="hash_abc123",
            pending_output=pending_output,
            session_state=session_state,
        )

        assert hook_result.allowed is False
        assert hook_result.pending_output_held is True

        # Verify output was held
        held = resume_hooks.get_pending_output_held("hash_abc123")
        assert held is not None
        assert held["pending_output"] == pending_output

        # Cleanup
        resume_hooks.release_pending_output("hash_abc123")


class TestResumeUnknownDeliveryStateManualReview:
    """Test that unknown delivery state triggers manual review."""

    def test_resume_unknown_delivery_state_manual_review(self) -> None:
        """Resume with unknown delivery state should require manual review."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            delivery_state_known=False,  # Unknown - FAIL_CLOSED_POLICY
        )

        pending_output = {"message": "test message"}

        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", pending_output)

        # Should be REVIEW_REQUIRED due to unknown delivery state
        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.DELIVERY_STATE_KNOWN in result.failed_checks
        assert result.pending_output_held is True

    def test_resume_unknown_delivery_state_no_auto_delivery(self) -> None:
        """Resume with unknown delivery state must NOT auto-deliver (FAIL_CLOSED_POLICY)."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            delivery_state_known=False,
        )

        pending_output = {"message": "test message", "auto_deliver": True}

        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", pending_output)

        # FAIL_CLOSED_POLICY: must NOT auto-deliver when state is unknown
        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert result.pending_output_held is True


class TestResumeRechecksAllowlist:
    """Test that resume re-checks allowlist conditions."""

    def test_resume_rechecks_allowlist_valid(self) -> None:
        """Resume should pass when allowlist is valid."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            delivery_state_known=True,
        )

        hook_result = resume_hooks.check_pending_output_reconciliation(
            session_key_hash="hash_abc123",
            pending_output={"message": "test"},
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            platform_allowlist_valid=True,
        )

        assert hook_result.allowed is True
        assert "platform_allowlist" not in hook_result.reason_codes

    def test_resume_rechecks_allowlist_invalid(self) -> None:
        """Resume should fail when allowlist is invalid."""
        resume_hooks.clear_pending_output_hold_store()

        hook_result = resume_hooks.check_pending_output_reconciliation(
            session_key_hash="hash_abc123",
            pending_output={"message": "test"},
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            platform_allowlist_valid=False,  # Invalid
        )

        assert hook_result.allowed is False
        assert "platform_allowlist" in hook_result.reason_codes
        assert hook_result.pending_output_held is True

        # Cleanup
        resume_hooks.release_pending_output("hash_abc123")


class TestResumeRechecksTTLAndPause:
    """Test that resume re-checks TTL and pause conditions."""

    def test_resume_expired_continuity_marker_ttl(self) -> None:
        """Resume should fail when continuity marker TTL is expired."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            delivery_state_known=True,
        )

        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", {"message": "test"})

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.CONTINUITY_MARKER_TTL in result.failed_checks

    def test_resume_paused_continuity_scope(self) -> None:
        """Resume should fail when continuity scope is paused."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_scope_paused=True,  # Paused
            delivery_state_known=True,
        )

        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", {"message": "test"})

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.CONTINUITY_SCOPE_PAUSE in result.failed_checks

    def test_resume_max_followup_attempts_reached(self) -> None:
        """Resume should fail when max followup attempts are reached."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            followup_attempt_count=3,  # Max reached
            delivery_state_known=True,
        )

        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", {"message": "test"})

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.FOLLOWUP_ATTEMPT_COUNT in result.failed_checks

    def test_resume_safety_review_required(self) -> None:
        """Resume should fail when safety review is required."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            safety_review_required=True,  # Needs review
            delivery_state_known=True,
        )

        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", {"message": "test"})

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.SAFETY_REVIEW_STATE in result.failed_checks

    def test_resume_output_sanitizer_blocked(self) -> None:
        """Resume should fail when output sanitizer blocks."""
        session_state = SessionResumeState(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            output_sanitizer_clean=False,  # Blocked
            delivery_state_known=True,
        )

        reconciler = ResumeReconciliation(session_state)
        result = reconciler.reconcile("hash_abc123", {"message": "test"})

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.OUTPUT_SANITIZER in result.failed_checks


class TestResumeHookIntegration:
    """Integration tests for resume hooks with Hermes plugin hooks."""

    def test_on_checkpoint_resume_calls_reconciliation(self) -> None:
        """on_checkpoint_resume should call check_pending_output_reconciliation."""
        resume_hooks.clear_pending_output_hold_store()

        result = resume_hooks.on_checkpoint_resume(
            session_key_hash="hash_checkpoint",
            checkpoint_data={"message": "checkpoint test"},
        )

        # Should return a valid hook result
        assert result is not None
        assert result.event == resume_hooks.ResumeHookEvent.SESSION_RESUME
        assert result.session_key_hash == "hash_checkpoint"

    def test_hold_and_release_pending_output(self) -> None:
        """Test holding and releasing pending output."""
        resume_hooks.clear_pending_output_hold_store()

        session_key_hash = "hash_test_123"
        pending_output = {"message": "test message"}

        # Initially nothing held
        assert resume_hooks.get_pending_output_held(session_key_hash) is None

        # Hold it
        resume_hooks.hold_pending_output(session_key_hash, pending_output)
        held = resume_hooks.get_pending_output_held(session_key_hash)
        assert held is not None
        assert held["pending_output"] == pending_output

        # Release it
        resume_hooks.release_pending_output(session_key_hash)
        assert resume_hooks.get_pending_output_held(session_key_hash) is None

    def test_build_session_resume_state(self) -> None:
        """Test building session resume state from parameters."""
        state = resume_hooks.build_session_resume_state(
            subject_id="subject_123",
            gumi_instance_id="gumi_abc",
            hermes_profile_id="hermes_xyz",
            session_key_hash="hash_abc123",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_marker_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            continuity_scope_paused=False,
            followup_attempt_count=1,
            safety_review_required=False,
            behavior_policy_patch_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )

        assert state.subject_id == "subject_123"
        assert state.gumi_instance_id == "gumi_abc"
        assert state.hermes_profile_id == "hermes_xyz"
        assert state.session_key_hash == "hash_abc123"
        assert state.platform_allowlist_valid is True
        assert state.delivery_enabled is True
        assert state.continuity_marker_active is True
        assert state.continuity_scope_paused is False
        assert state.followup_attempt_count == 1
        assert state.safety_review_required is False
        assert state.output_sanitizer_clean is True
        assert state.delivery_state_known is True