"""
Handoff Gate, Authorization for Hermes /handoff feature.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from relic.chronicle.enums import EventCategory, Severity
from relic.persistence import PrivacyLevel
from relic.hermes_adapter.chronicle_helper import emit_governance_event


class HandoffRisk(str, Enum):
    """Risk level for handoff operation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HandoffDecisionValue(str, Enum):
    """Handoff gate decision."""
    AUTHORIZED = "AUTHORIZED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class HandoffRequest:
    """Handoff request from Hermes."""
    source_session_id: str
    source_profile_id: str
    target_profile_id: str
    target_model: Optional[str] = None
    reason: Optional[str] = None
    actor_type: str = "user"
    actor_id: Optional[str] = None
    preserve_context: bool = True
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "source_session_id": self.source_session_id,
            "source_profile_id": self.source_profile_id,
            "target_profile_id": self.target_profile_id,
            "target_model": self.target_model,
            "reason": self.reason,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "preserve_context": self.preserve_context,
            "requested_at": self.requested_at.isoformat(),
        }


@dataclass(frozen=True)
class HandoffDecision:
    """Handoff gate decision with policy snapshot."""
    handoff_id: str
    decision: HandoffDecisionValue
    risk_level: HandoffRisk
    reason_codes: list[str]
    subject_ref: str
    policy_snapshot_ref: Optional[str] = None
    context_preservation: bool = True
    risk_boundary_crossed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "handoff_id": self.handoff_id,
            "decision": self.decision.value,
            "risk_level": self.risk_level.value,
            "reason_codes": self.reason_codes,
            "subject_ref": self.subject_ref,
            "policy_snapshot_ref": self.policy_snapshot_ref,
            "context_preservation": self.context_preservation,
            "risk_boundary_crossed": self.risk_boundary_crossed,
            "created_at": self.created_at.isoformat(),
        }


class HandoffGate:
    """Gatekeeper for Hermes handoff operations."""

    def __init__(self, emit_events: bool = True):
        self.emit_events = emit_events
        self._policy_cache: dict[str, Any] = {}

    def evaluate(self, request: HandoffRequest, subject_ref: str) -> HandoffDecision:
        """Evaluate handoff request."""
        handoff_id = f"handoff-{uuid4().hex[:12]}"
        reason_codes: list[str] = []
        risk_level = HandoffRisk.LOW
        risk_boundary_crossed = False

        if self._is_cross_subject(request):
            risk_level = HandoffRisk.HIGH
            risk_boundary_crossed = True
            reason_codes.append("cross_subject_handoff")

        if self._is_untrusted_model_transition(request):
            risk_level = HandoffRisk.CRITICAL if risk_level == HandoffRisk.HIGH else HandoffRisk.MEDIUM
            reason_codes.append("untrusted_model_transition")

        if self._has_active_safety_review(subject_ref):
            return HandoffDecision(
                handoff_id=handoff_id,
                decision=HandoffDecisionValue.BLOCKED,
                risk_level=HandoffRisk.HIGH,
                reason_codes=["active_safety_review"],
                subject_ref=subject_ref,
                risk_boundary_crossed=True,
            )

        if not request.preserve_context:
            reason_codes.append("context_not_preserved")
            if risk_level == HandoffRisk.LOW:
                risk_level = HandoffRisk.MEDIUM

        if risk_level == HandoffRisk.CRITICAL:
            decision = HandoffDecisionValue.BLOCKED
        elif risk_level == HandoffRisk.HIGH or risk_boundary_crossed:
            decision = HandoffDecisionValue.REVIEW_REQUIRED
        else:
            decision = HandoffDecisionValue.AUTHORIZED

        handoff_decision = HandoffDecision(
            handoff_id=handoff_id,
            decision=decision,
            risk_level=risk_level,
            reason_codes=reason_codes,
            subject_ref=subject_ref,
            policy_snapshot_ref=self._get_policy_snapshot_ref(subject_ref),
            context_preservation=request.preserve_context,
            risk_boundary_crossed=risk_boundary_crossed,
        )

        if self.emit_events:
            event_type = "handoff_authorized"
            if decision == HandoffDecisionValue.BLOCKED:
                event_type = "handoff_blocked"
            elif decision == HandoffDecisionValue.REVIEW_REQUIRED:
                event_type = "handoff_requested"

            # Use DECISION category and SAFE sensitivity for Chronicle compatibility
            from relic.chronicle.schema import Event
            from relic.chronicle.emitter import emit_event
            import hashlib
            import uuid as uuid_lib

            payload = {
                "handoff_id": handoff_id,
                "decision": decision.value,
                "risk_level": risk_level.value,
                "source_profile": request.source_profile_id,
                "target_profile": request.target_profile_id,
                "reason_codes": reason_codes,
            }
            payload_hash = f"sha256:{hashlib.sha256(str(payload).encode()).hexdigest()[:32]}"

            event = Event(
                event_type=event_type,
                event_category=EventCategory.DECISION,
                trace_id=uuid_lib.uuid4(),
                subject_id=subject_ref,
                source_module="relic.hermes_adapter.handoff_gate",
                payload=payload,
                payload_hash=payload_hash,
                payload_redacted=True,
                tags=[f"handoff:{handoff_id}"],
                sensitivity=PrivacyLevel.SAFE,
            )
            emit_event(event)

        return handoff_decision

    def _is_cross_subject(self, request: HandoffRequest) -> bool:
        return False

    def _is_untrusted_model_transition(self, request: HandoffRequest) -> bool:
        return False

    def _has_active_safety_review(self, subject_ref: str) -> bool:
        return False

    def _get_policy_snapshot_ref(self, subject_ref: str) -> Optional[str]:
        return f"policy-snapshot-{subject_ref[:8]}"


_default_gate: Optional[HandoffGate] = None
_gate_lock = threading.Lock()


def get_handoff_gate() -> HandoffGate:
    """Get or create default HandoffGate."""
    global _default_gate
    if _default_gate is None:
        with _gate_lock:
            if _default_gate is None:
                _default_gate = HandoffGate()
    return _default_gate


def evaluate_handoff(request: HandoffRequest, subject_ref: str) -> HandoffDecision:
    """Evaluate handoff using default gate."""
    return get_handoff_gate().evaluate(request, subject_ref)
