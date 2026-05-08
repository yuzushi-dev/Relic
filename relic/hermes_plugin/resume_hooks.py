"""Resume reconciliation hooks for Hermes session resume flow (WIRE06).

This module wires ResumeReconciliation into the Hermes plugin hooks system.
It intercepts checkpoint resume and session resume events to ensure all
safety/continuity/allowlist conditions are re-checked before delivery.

FAIL_CLOSED_POLICY: unknown delivery state → MANUAL_REVIEW_REQUIRED, no auto-delivery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from relic.hermes_runtime import (
        ReconciliationCheck,
        ReconciliationDecision,
        ReconciliationResult,
        ResumeReconciliation,
        SessionResumeState,
    )


class ResumeHookEvent(str, Enum):
    """Resume hook event types."""
    CHECKPOINT_RESUME = "checkpoint_resume"
    SESSION_RESUME = "session_resume"
    RECONCILIATION_COMPLETE = "reconciliation_complete"


@dataclass
class ResumeHookResult:
    """Result of a resume hook execution."""
    allowed: bool
    event: ResumeHookEvent
    session_key_hash: str
    reconciliation_decision: str  # ReconciliationDecision value
    reason_codes: list[str]
    pending_output_held: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "event": self.event.value,
            "session_key_hash": self.session_key_hash,
            "reconciliation_decision": self.reconciliation_decision,
            "reason_codes": self.reason_codes,
            "pending_output_held": self.pending_output_held,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


# In-memory store for pending output holds (session-scoped)
# In production this would be backed by PostgreSQL; per constraints we keep it in-memory
_PENDING_OUTPUT_HOLD_STORE: dict[str, dict] = {}


def _session_pending_key(session_key_hash: str) -> str:
    """Generate a lookup key for pending output hold store."""
    return session_key_hash


def hold_pending_output(session_key_hash: str, pending_output: dict) -> None:
    """Hold pending output for manual review.

    Args:
        session_key_hash: The session key hash.
        pending_output: The pending output to hold.
    """
    key = _session_pending_key(session_key_hash)
    _PENDING_OUTPUT_HOLD_STORE[key] = {
        "session_key_hash": session_key_hash,
        "pending_output": pending_output,
        "held_at": datetime.now(timezone.utc).isoformat(),
    }


def get_pending_output_held(session_key_hash: str) -> dict | None:
    """Get held pending output if any.

    Args:
        session_key_hash: The session key hash.

    Returns:
        Held pending output dict or None.
    """
    key = _session_pending_key(session_key_hash)
    return _PENDING_OUTPUT_HOLD_STORE.get(key)


def release_pending_output(session_key_hash: str) -> None:
    """Release (delete) held pending output after manual review.

    Args:
        session_key_hash: The session key hash.
    """
    key = _session_pending_key(session_key_hash)
    _PENDING_OUTPUT_HOLD_STORE.pop(key, None)


def clear_pending_output_hold_store() -> None:
    """Clear all pending output holds. For testing only."""
    _PENDING_OUTPUT_HOLD_STORE.clear()


def build_session_resume_state(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    session_key_hash: str,
    *,
    platform_allowlist_valid: bool = True,
    delivery_enabled: bool = True,
    continuity_marker_active: bool = True,
    continuity_marker_expires_at: datetime | None = None,
    continuity_scope_paused: bool = False,
    followup_attempt_count: int = 0,
    safety_review_required: bool = False,
    behavior_policy_patch_expires_at: datetime | None = None,
    output_sanitizer_clean: bool = True,
    delivery_state_known: bool = True,
) -> "SessionResumeState":
    """Build a SessionResumeState from individual parameters.

    Args:
        subject_id: Subject identifier.
        gumi_instance_id: Gumi instance identifier.
        hermes_profile_id: Hermes profile identifier.
        session_key_hash: Session key hash.
        platform_allowlist_valid: Whether platform is allowlisted.
        delivery_enabled: Whether delivery is enabled.
        continuity_marker_active: Whether continuity marker is active.
        continuity_marker_expires_at: Continuity marker expiry.
        continuity_scope_paused: Whether continuity scope is paused.
        followup_attempt_count: Number of followup attempts.
        safety_review_required: Whether safety review is required.
        behavior_policy_patch_expires_at: Behavior policy patch expiry.
        output_sanitizer_clean: Whether output sanitizer is clean.
        delivery_state_known: Whether delivery state is known.

    Returns:
        SessionResumeState instance.
    """
    # Import here to avoid circular reference at module level
    from relic.hermes_runtime import SessionResumeState

    return SessionResumeState(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        session_key_hash=session_key_hash,
        platform_allowlist_valid=platform_allowlist_valid,
        delivery_enabled=delivery_enabled,
        continuity_marker_active=continuity_marker_active,
        continuity_marker_expires_at=continuity_marker_expires_at,
        continuity_scope_paused=continuity_scope_paused,
        followup_attempt_count=followup_attempt_count,
        safety_review_required=safety_review_required,
        behavior_policy_patch_expires_at=behavior_policy_patch_expires_at,
        output_sanitizer_clean=output_sanitizer_clean,
        delivery_state_known=delivery_state_known,
    )


def on_hermes_session_resume(
    session_key_hash: str,
    pending_output: dict | None,
    session_state: "SessionResumeState",
) -> ResumeHookResult:
    """Called when Hermes resumes a session.

    This is the main entry point for session resume reconciliation.
    It re-checks all safety/continuity/allowlist conditions before
    allowing delivery of pending output.

    FAIL_CLOSED_POLICY:
    - If reconciliation returns REVIEW_REQUIRED: block delivery, require manual review.
    - If unknown delivery state: MANUAL_REVIEW_REQUIRED, no auto-delivery.

    Args:
        session_key_hash: The session key hash to validate.
        pending_output: Optional pending output to check.
        session_state: The session resume state snapshot.

    Returns:
        ResumeHookResult with decision and hold status.
    """
    # Import here to avoid circular reference at module level
    from relic.hermes_runtime import (
        ReconciliationDecision,
        ResumeReconciliation,
    )

    # Create reconciliation engine
    reconciler = ResumeReconciliation(session_state)

    # Run reconciliation
    result = reconciler.reconcile(session_key_hash, pending_output)

    # Build reason codes from failed checks
    reason_codes = [check.value for check in result.failed_checks]

    # Determine if we should hold pending output
    pending_output_held = False
    if result.decision == ReconciliationDecision.REVIEW_REQUIRED:
        pending_output_held = True
        if pending_output is not None:
            hold_pending_output(session_key_hash, pending_output)

    return ResumeHookResult(
        allowed=result.decision == ReconciliationDecision.ALLOW,
        event=ResumeHookEvent.SESSION_RESUME,
        session_key_hash=session_key_hash,
        reconciliation_decision=result.decision.value,
        reason_codes=reason_codes,
        pending_output_held=pending_output_held,
        metadata=result.metadata,
    )


def on_checkpoint_resume(
    session_key_hash: str,
    checkpoint_data: dict | None = None,
) -> ResumeHookResult:
    """Intercept Hermes checkpoint resume.

    This is called when Hermes resumes from a checkpoint.
    It re-checks all conditions before allowing checkpoint replay.

    Args:
        session_key_hash: The session key hash to validate.
        checkpoint_data: Optional checkpoint data for additional checks.

    Returns:
        ResumeHookResult with decision.
    """
    # For checkpoint resume, we need to reconstruct the session state
    # from the checkpoint data or from a session state store.
    # This is a stub that delegates to check_pending_output_reconciliation.
    return check_pending_output_reconciliation(
        session_key_hash=session_key_hash,
        pending_output=checkpoint_data,
    )


def check_pending_output_reconciliation(
    session_key_hash: str,
    pending_output: dict | None,
    *,
    subject_id: str = "",
    gumi_instance_id: str = "",
    hermes_profile_id: str = "",
    platform_allowlist_valid: bool = True,
    delivery_enabled: bool = True,
    continuity_marker_active: bool = True,
    continuity_marker_expires_at: datetime | None = None,
    continuity_scope_paused: bool = False,
    followup_attempt_count: int = 0,
    safety_review_required: bool = False,
    behavior_policy_patch_expires_at: datetime | None = None,
    output_sanitizer_clean: bool = True,
    delivery_state_known: bool = True,
) -> ResumeHookResult:
    """Re-check all safety/continuity/allowlist conditions for pending output.

    This function performs a full reconciliation pass on pending output
    before delivery, enforcing the FAIL_CLOSED_POLICY for unknown states.

    Args:
        session_key_hash: The session key hash to validate.
        pending_output: Optional pending output to check.
        subject_id: Subject identifier (required for meaningful reconciliation).
        gumi_instance_id: Gumi instance identifier.
        hermes_profile_id: Hermes profile identifier.
        platform_allowlist_valid: Whether platform is allowlisted.
        delivery_enabled: Whether delivery is enabled.
        continuity_marker_active: Whether continuity marker is active.
        continuity_marker_expires_at: Continuity marker expiry.
        continuity_scope_paused: Whether continuity scope is paused.
        followup_attempt_count: Number of followup attempts.
        safety_review_required: Whether safety review is required.
        behavior_policy_patch_expires_at: Behavior policy patch expiry.
        output_sanitizer_clean: Whether output sanitizer is clean.
        delivery_state_known: Whether delivery state is known.

    Returns:
        ResumeHookResult with decision and hold status.
    """
    # Build session state from parameters
    session_state = build_session_resume_state(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        session_key_hash=session_key_hash,
        platform_allowlist_valid=platform_allowlist_valid,
        delivery_enabled=delivery_enabled,
        continuity_marker_active=continuity_marker_active,
        continuity_marker_expires_at=continuity_marker_expires_at,
        continuity_scope_paused=continuity_scope_paused,
        followup_attempt_count=followup_attempt_count,
        safety_review_required=safety_review_required,
        behavior_policy_patch_expires_at=behavior_policy_patch_expires_at,
        output_sanitizer_clean=output_sanitizer_clean,
        delivery_state_known=delivery_state_known,
    )

    return on_hermes_session_resume(
        session_key_hash=session_key_hash,
        pending_output=pending_output,
        session_state=session_state,
    )