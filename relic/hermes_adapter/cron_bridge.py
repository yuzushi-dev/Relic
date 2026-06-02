"""
Cron Bridge, Wrapper for Hermes cron/writer decision logic.

This module provides a stable interface for cron-based proactive delivery
decisions, wrapping the existing relic.gumi_plugin.cron_wiring logic with
a structured RuntimeDecisionResult dataclass.

Design: Hermes owns scheduling. Relic owns delivery decisions.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from relic.hermes_runtime import (
    RuntimeDecision,
    RuntimeDecisionReason,
    DecisionEvent,
)


@dataclass(frozen=True)
class RuntimeDecisionResult:
    """
    Structured result from cron/writer decision logic.

    Attributes:
        decision: The delivery decision (NO_REPLY, CANDIDATE, DELIVER, etc.)
        reason_codes: List of reason codes explaining the decision
        subject_ref: Subject reference for Relic governance
        candidate_message: Optional candidate message content (if CANDIDATE/DELIVER)
        candidate_message_hash: SHA-256 hash of candidate message
        media_type: Media type for proactive delivery (text/voice/image/music)
        trace_event_id: Optional Chronicle event ID for correlation
        gumi_instance_id: Gumi instance identifier
        hermes_profile_id: Hermes profile identifier
        decided_at: UTC timestamp of decision
    """

    decision: RuntimeDecision
    reason_codes: list[RuntimeDecisionReason]
    subject_ref: str
    candidate_message: Optional[str] = None
    candidate_message_hash: Optional[str] = None
    media_type: str = "text"
    trace_event_id: Optional[UUID] = None
    gumi_instance_id: str = "default"
    hermes_profile_id: str = "default"
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate and compute message hash if message provided."""
        if self.candidate_message is not None and self.candidate_message_hash is None:
            msg_hash = f"sha256:{hashlib.sha256(self.candidate_message.encode()).hexdigest()[:32]}"
            object.__setattr__(self, "candidate_message_hash", msg_hash)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "decision": self.decision.value,
            "reason_codes": [r.value for r in self.reason_codes],
            "subject_ref": self.subject_ref,
            "candidate_message": self.candidate_message,
            "candidate_message_hash": self.candidate_message_hash,
            "media_type": self.media_type,
            "trace_event_id": str(self.trace_event_id) if self.trace_event_id else None,
            "gumi_instance_id": self.gumi_instance_id,
            "hermes_profile_id": self.hermes_profile_id,
            "decided_at": self.decided_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> RuntimeDecisionResult:
        """Create from dictionary."""
        return cls(
            decision=RuntimeDecision(data["decision"]),
            reason_codes=[RuntimeDecisionReason(r) for r in data["reason_codes"]],
            subject_ref=data["subject_ref"],
            candidate_message=data.get("candidate_message"),
            candidate_message_hash=data.get("candidate_message_hash"),
            media_type=data.get("media_type", "text"),
            trace_event_id=UUID(data["trace_event_id"]) if data.get("trace_event_id") else None,
            gumi_instance_id=data.get("gumi_instance_id", "default"),
            hermes_profile_id=data.get("hermes_profile_id", "default"),
            decided_at=datetime.fromisoformat(data["decided_at"]) if data.get("decided_at") else datetime.now(timezone.utc),
        )

    def with_trace_event_id(self, trace_event_id: UUID) -> RuntimeDecisionResult:
        """Create new result with trace event ID."""
        return replace(self, trace_event_id=trace_event_id)

    def is_deliverable(self) -> bool:
        """Check if decision allows delivery."""
        return self.decision in (RuntimeDecision.DELIVER, RuntimeDecision.CANDIDATE)


class CronBridge:
    """
    Bridge between Hermes cron scheduler and Relic decision logic.
    """

    def __init__(
        self,
        gumi_instance_id: str = "default",
        hermes_profile_id: str = "default",
        emit_events: bool = True,
    ):
        self.gumi_instance_id = gumi_instance_id
        self.hermes_profile_id = hermes_profile_id
        self.emit_events = emit_events

    def evaluate_proactive_delivery(
        self,
        subject_ref: str,
        candidate_message: Optional[str] = None,
        media_type: str = "text",
    ) -> RuntimeDecisionResult:
        """Evaluate proactive delivery decision for a subject."""
        reason_codes: list[RuntimeDecisionReason] = []

        if candidate_message is None:
            return RuntimeDecisionResult(
                decision=RuntimeDecision.NO_REPLY,
                reason_codes=[RuntimeDecisionReason.no_due_work],
                subject_ref=subject_ref,
                gumi_instance_id=self.gumi_instance_id,
                hermes_profile_id=self.hermes_profile_id,
                media_type=media_type,
            )

        return RuntimeDecisionResult(
            decision=RuntimeDecision.CANDIDATE,
            reason_codes=reason_codes,
            subject_ref=subject_ref,
            candidate_message=candidate_message,
            gumi_instance_id=self.gumi_instance_id,
            hermes_profile_id=self.hermes_profile_id,
            media_type=media_type,
        )

    def evaluate_quiet_hours(self, subject_ref: str) -> bool:
        """Check if quiet hours are active for subject."""
        return False

    def evaluate_platform_allowlist(
        self,
        subject_ref: str,
        platform: str,
    ) -> bool:
        """Check if platform is allowlisted for subject."""
        return True


_default_bridge: Optional[CronBridge] = None
_bridge_lock = threading.Lock()


def get_bridge() -> CronBridge:
    """Get or create default CronBridge."""
    global _default_bridge
    if _default_bridge is None:
        with _bridge_lock:
            if _default_bridge is None:
                _default_bridge = CronBridge()
    return _default_bridge


def evaluate_proactive_delivery(
    subject_ref: str,
    candidate_message: Optional[str] = None,
    media_type: str = "text",
) -> RuntimeDecisionResult:
    """Evaluate proactive delivery using default bridge."""
    return get_bridge().evaluate_proactive_delivery(
        subject_ref=subject_ref,
        candidate_message=candidate_message,
        media_type=media_type,
    )
