"""
Approvals, Approval event normalization for Hermes.

This module normalizes approval requests and resolutions from Hermes,
emitting canonical Chronicle events for audit.

Design: Hermes requests approvals. Relic records and governs approvals.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from relic.hermes_adapter.chronicle_helper import emit_governance_event
from relic.hermes_adapter.state_store import StateStore


class ApprovalType(str, Enum):
    """Type of approval request."""
    DELIVERY = "delivery"
    HANDOFF = "handoff"
    CONTEXT_EXPANSION = "context_expansion"
    TOOL_EXECUTION = "tool_execution"
    PROFILE_CHANGE = "profile_change"
    DATA_EXPORT = "data_export"


class ApprovalDecision(str, Enum):
    """Approval decision."""
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    REVOKED = "revoked"


class RiskLevel(str, Enum):
    """Risk level for approval request."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ApprovalRequest:
    """
    Approval request from Hermes.

    Attributes:
        approval_id: Unique approval identifier
        approval_type: Type of approval requested
        action_description: Human-readable description of action
        risk_level: Assessed risk level
        subject_ref: Subject reference
        actor_type: Who initiated (user/system/admin)
        actor_id: Actor identifier
        expires_at: Optional expiration timestamp
        metadata: Additional context
        requested_at: Request timestamp
    """
    approval_id: str
    approval_type: ApprovalType
    action_description: str
    risk_level: RiskLevel
    subject_ref: str
    actor_type: str = "user"
    actor_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "approval_type": self.approval_type.value,
            "action_description": self.action_description,
            "risk_level": self.risk_level.value,
            "subject_ref": self.subject_ref,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
            "requested_at": self.requested_at.isoformat(),
        }

    @classmethod
    def create(
        cls,
        approval_type: ApprovalType,
        action_description: str,
        risk_level: RiskLevel,
        subject_ref: str,
        actor_type: str = "user",
        actor_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "ApprovalRequest":
        """Create a new approval request."""
        return cls(
            approval_id=f"approval-{uuid4().hex[:12]}",
            approval_type=approval_type,
            action_description=action_description,
            risk_level=risk_level,
            subject_ref=subject_ref,
            actor_type=actor_type,
            actor_id=actor_id,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class ApprovalResolution:
    """
    Approval resolution.

    Attributes:
        approval_id: Reference to original approval request
        decision: Approval decision
        resolved_by: Who resolved (user/system)
        resolved_by_id: Resolver identifier
        resolution_notes: Optional notes explaining decision
        resolved_at: Resolution timestamp
    """
    approval_id: str
    decision: ApprovalDecision
    resolved_by: str
    resolved_by_id: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "decision": self.decision.value,
            "resolved_by": self.resolved_by,
            "resolved_by_id": self.resolved_by_id,
            "resolution_notes": self.resolution_notes,
            "resolved_at": self.resolved_at.isoformat(),
        }


class ApprovalManager:
    """
    Manager for approval lifecycle.

    This manager tracks approval requests and resolutions,
    emitting Chronicle events for audit.

    Args:
        emit_events: Whether to emit Chronicle events (default: True)
        auto_expire_minutes: Minutes after which requests auto-expire (default: 60)
    """

    def __init__(
        self,
        emit_events: bool = True,
        auto_expire_minutes: int = 60,
        persist: bool = False,
    ):
        self.emit_events = emit_events
        self.auto_expire_minutes = auto_expire_minutes
        self._persist_store: Optional[StateStore] = (
            StateStore("approval_pending") if persist else None
        )
        self._pending: dict[str, ApprovalRequest] = {}
        self._resolved: dict[str, ApprovalResolution] = {}
        if self._persist_store is not None:
            self._load_pending_from_store()

    def _load_pending_from_store(self) -> None:
        """Restore pending approvals from durable store on startup."""
        import json as _json
        for approval_id, raw in self._persist_store.all().items():
            try:
                data = _json.loads(raw) if isinstance(raw, str) else raw
                req = ApprovalRequest(
                    approval_id=data["approval_id"],
                    approval_type=ApprovalType(data["approval_type"]),
                    action_description=data["action_description"],
                    risk_level=RiskLevel(data["risk_level"]),
                    subject_ref=data["subject_ref"],
                    actor_type=data.get("actor_type", "user"),
                    actor_id=data.get("actor_id"),
                    metadata=data.get("metadata", {}),
                )
                self._pending[approval_id] = req
            except Exception:
                pass

    def request(self, request: ApprovalRequest) -> None:
        """
        Register approval request.

        Args:
            request: Approval request to register
        """
        self._pending[request.approval_id] = request
        if self._persist_store is not None:
            self._persist_store.set(request.approval_id, request.to_dict())

        if self.emit_events:
            emit_governance_event(
                subject_ref=request.subject_ref,
                event_type="approval_requested",
                payload={
                    "approval_id": request.approval_id,
                    "approval_type": request.approval_type.value,
                    "action_description": request.action_description,
                    "risk_level": request.risk_level.value,
                    "actor_type": request.actor_type,
                },
            )

    def resolve(self, resolution: ApprovalResolution) -> None:
        """
        Register approval resolution.

        Args:
            resolution: Approval resolution to register
        """
        subject_ref = self._get_subject_ref(resolution.approval_id)

        if resolution.approval_id in self._pending:
            del self._pending[resolution.approval_id]
            if self._persist_store is not None:
                self._persist_store.delete(resolution.approval_id)
        self._resolved[resolution.approval_id] = resolution

        if self.emit_events:
            event_type = "approval_granted"
            if resolution.decision == ApprovalDecision.DENIED:
                event_type = "approval_denied"

            emit_governance_event(
                subject_ref=subject_ref,
                event_type=event_type,
                payload={
                    "approval_id": resolution.approval_id,
                    "decision": resolution.decision.value,
                    "resolved_by": resolution.resolved_by,
                    "resolution_notes": resolution.resolution_notes,
                },
            )

    def get_pending(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get pending approval request."""
        return self._pending.get(approval_id)

    def get_resolved(self, approval_id: str) -> Optional[ApprovalResolution]:
        """Get resolved approval."""
        return self._resolved.get(approval_id)

    def _get_subject_ref(self, approval_id: str) -> str:
        """Get subject reference from approval ID."""
        if approval_id in self._pending:
            return self._pending[approval_id].subject_ref
        if approval_id in self._resolved:
            # Would need to store subject_ref in resolved too
            return "unknown"
        return "unknown"


# Convenience functions

_default_manager: Optional[ApprovalManager] = None
_manager_lock = threading.Lock()


def get_approval_manager() -> ApprovalManager:
    """Get or create default ApprovalManager."""
    global _default_manager
    if _default_manager is None:
        with _manager_lock:
            if _default_manager is None:
                _default_manager = ApprovalManager()
    return _default_manager


def request_approval(
    approval_type: ApprovalType,
    action_description: str,
    risk_level: RiskLevel,
    subject_ref: str,
    actor_type: str = "user",
    metadata: Optional[dict] = None,
) -> ApprovalRequest:
    """Create and register approval request."""
    request = ApprovalRequest.create(
        approval_type=approval_type,
        action_description=action_description,
        risk_level=risk_level,
        subject_ref=subject_ref,
        actor_type=actor_type,
        metadata=metadata,
    )
    get_approval_manager().request(request)
    return request


def resolve_approval(
    approval_id: str,
    decision: ApprovalDecision,
    resolved_by: str,
    resolved_by_id: Optional[str] = None,
    resolution_notes: Optional[str] = None,
) -> ApprovalResolution:
    """Register approval resolution."""
    resolution = ApprovalResolution(
        approval_id=approval_id,
        decision=decision,
        resolved_by=resolved_by,
        resolved_by_id=resolved_by_id,
        resolution_notes=resolution_notes,
    )
    get_approval_manager().resolve(resolution)
    return resolution
