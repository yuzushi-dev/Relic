"""
PolicyGate, Base abstraction for Hermes adapter policy gates.

All governance gates (handoff, approval, cron, source, cache) share:
- A typed Request dataclass
- A typed Decision dataclass that extends PolicyDecision
- reason_codes vocabulary
- risk_level classification
- Chronicle emission

This module provides the shared base so future gates don't reinvent the pattern.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generic, Protocol, TypeVar

RequestT = TypeVar("RequestT")
DecisionT = TypeVar("DecisionT")


@dataclass(frozen=True)
class PolicyDecision:
    """Base for all adapter gate decisions.

    Subclass this and add gate-specific fields.  reason_codes uses a
    shared vocabulary so cross-gate aggregation is possible without
    string parsing.
    """
    decision_id: str
    subject_ref: str
    authorized: bool
    reason_codes: list[str]
    risk_level: str  # "low" | "medium" | "high" | "critical"
    policy_snapshot_ref: str
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "subject_ref": self.subject_ref,
            "authorized": self.authorized,
            "reason_codes": self.reason_codes,
            "risk_level": self.risk_level,
            "policy_snapshot_ref": self.policy_snapshot_ref,
            "decided_at": self.decided_at.isoformat(),
        }

    @classmethod
    def _new_id(cls, prefix: str = "decision") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"


class PolicyGate(Protocol[RequestT, DecisionT]):
    """Protocol for all adapter policy gates.

    Implementing this protocol enables uniform:
    - evaluation (evaluate → Decision)
    - Chronicle emission
    - cross-gate composition
    """

    def evaluate(self, request: RequestT, subject_ref: str) -> DecisionT:
        """Evaluate request for subject. Emit Chronicle event. Return decision."""
        ...


# ---------------------------------------------------------------------------
# Shared reason code vocabulary
# ---------------------------------------------------------------------------

class ReasonCode:
    """Canonical reason code strings. Use these instead of free-form strings."""

    # Authorization
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"

    # Risk
    CROSS_SUBJECT = "cross_subject"
    UNTRUSTED_MODEL = "untrusted_model_transition"
    ACTIVE_SAFETY_REVIEW = "active_safety_review"
    CONTEXT_NOT_PRESERVED = "context_not_preserved"
    HIGH_RISK_APPROVAL_TYPE = "high_risk_approval_type"

    # Consent / source
    CONSENT_NOT_GRANTED = "consent_not_granted"
    CONSENT_EXPIRED = "consent_expired"
    SOURCE_NOT_EVIDENCE_ELIGIBLE = "source_not_evidence_eligible"
    PLATFORM_NOT_ALLOWLISTED = "platform_not_allowlisted"

    # Delivery / cron
    QUIET_HOURS = "quiet_hours"
    RATE_LIMITED = "rate_limited"
    FACET_GATED = "facet_gated"
    NO_CANDIDATE = "no_candidate"

    # Cache
    POLICY_CHANGED = "policy_changed"
    PROFILE_CHANGED = "profile_changed"
    TTL_EXPIRED = "ttl_expired"
    SECTION_NOT_CACHEABLE = "section_not_cacheable"
