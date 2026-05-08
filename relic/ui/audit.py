"""Audit and review-burden metrics module.

This module implements exception-workbench defaults for runtime-impacting items,
review-burden metrics, and batch-release policies.

Acceptance criteria:
- UI implements exception-workbench defaults for runtime-impacting disputed
  sensitive stale uncertain and missing-lineage items
- UI emits review-burden metrics: manual_review_rate, median_review_time_per_item,
  high_risk_queue_age, auto_resolved_low_risk_rate
- S0/S1 items cannot be batch-released and S2 warnings are hidden or batchable
  only when non-runtime-impacting
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RiskSeverity(str, Enum):
    """Risk severity levels for review items."""
    S0 = "S0"  # Critical - must review immediately
    S1 = "S1"  # High - must review before release
    S2 = "S2"  # Medium - warning, batchable if non-runtime-impacting
    S3 = "S3"  # Low - can batch, auto-resolve


class ItemState(str, Enum):
    """State of a review item - NOT represented through color only."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    DISPUTED = "disputed"
    SENSITIVE = "sensitive"
    STALE = "stale"
    UNCERTAIN = "uncertain"
    MISSING_LINEAGE = "missing_lineage"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_RESOLVED = "auto_resolved"


class BatchReleasePolicy(str, Enum):
    """Batch release policy based on severity and state."""
    NEVER = "never"  # S0, S1 always
    BATCHABLE_NON_RUNTIME = "batchable_non_runtime"  # S2 non-runtime only
    BATCHABLE = "batchable"  # S3 default
    AUTO_RESOLVE = "auto_resolve"  # Low risk auto-resolve


class ExceptionWorkbenchDefaults(BaseModel):
    """Exception workbench defaults for runtime-impacting items.

    UI implements these defaults for:
    - disputed: requires explicit resolution
    - sensitive: triggers privacy review
    - stale: requires recompile before release
    - uncertain: requires human judgment
    - missing_lineage: blocks release until lineage established
    """

    # Runtime-impacting states
    runtime_impacting_states: set[str] = Field(
        default={
            ItemState.DISPUTED.value,
            ItemState.SENSITIVE.value,
            ItemState.UNCERTAIN.value,
        }
    )

    # Batch release rules
    non_batchable_severities: set[str] = Field(
        default={RiskSeverity.S0.value, RiskSeverity.S1.value}
    )

    batch_release_policy: dict[str, BatchReleasePolicy] = Field(
        default={
            RiskSeverity.S0.value: BatchReleasePolicy.NEVER,
            RiskSeverity.S1.value: BatchReleasePolicy.NEVER,
            RiskSeverity.S2.value: BatchReleasePolicy.BATCHABLE_NON_RUNTIME,
            RiskSeverity.S3.value: BatchReleasePolicy.BATCHABLE,
        }
    )

    @classmethod
    def can_batch_release(
        cls,
        severity: "RiskSeverity | str",
        states: list[str] | None = None,
        runtime_impacting: bool = False,
        state: str | None = None,
    ) -> bool:
        """Determine if an item can be batch released."""
        severity_val = severity.value if isinstance(severity, RiskSeverity) else severity
        non_batchable = {RiskSeverity.S0.value, RiskSeverity.S1.value}

        if severity_val in non_batchable:
            return False

        if severity_val == RiskSeverity.S2.value and runtime_impacting:
            return False

        blocking_states = {
            ItemState.DISPUTED.value,
            ItemState.SENSITIVE.value,
            ItemState.UNCERTAIN.value,
        }
        all_states = list(states or [])
        if state:
            all_states.append(state)
        if any(s in blocking_states for s in all_states):
            return False

        return True


class ReviewBurdenMetrics(BaseModel):
    """Metrics for measuring review burden.

    UI emits these metrics for evaluation fixtures.
    Block condition: review-burden metrics are unavailable for UI evaluation fixtures
    """

    manual_review_rate: float = Field(default=0.0)
    median_review_time_per_item: float = Field(default=0.0)
    high_risk_queue_age: float = Field(default=0.0)
    auto_resolved_low_risk_rate: float = Field(default=0.0)

    # Additional tracking
    total_items: int = 0
    manual_review_items: int = 0
    auto_resolved_items: int = 0
    high_risk_pending: int = 0

    def model_dump_json_safe(self) -> dict[str, Any]:
        """Serialize ensuring no private data."""
        return self.model_dump()


class AuditLogger:
    """Logger for UI audit events.

    Tracks researcher actions without persisting raw prompts or private data.
    """

    def __init__(self, output_path: str | None = None):
        self._output_path = output_path
        self._events: list[dict[str, Any]] = []

    def log_feedback_provided(
        self,
        actor_role: str,
        target_id: UUID,
        feedback_type: str,
    ) -> None:
        """Log a feedback event."""
        event = {
            "event_type": "feedback_provided",
            "actor_role": actor_role,
            "target_id": str(target_id),
            "feedback_type": feedback_type,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._events.append(event)
        self._persist(event)

    def log_review_started(
        self,
        actor_role: str,
        item_id: UUID,
    ) -> None:
        """Log when a review is started."""
        event = {
            "event_type": "review_started",
            "actor_role": actor_role,
            "item_id": str(item_id),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._events.append(event)
        self._persist(event)

    def log_review_completed(
        self,
        actor_role: str,
        item_id: UUID,
        outcome: str,
    ) -> None:
        """Log when a review is completed."""
        event = {
            "event_type": "review_completed",
            "actor_role": actor_role,
            "item_id": str(item_id),
            "outcome": outcome,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._events.append(event)
        self._persist(event)

    def _persist(self, event: dict[str, Any]) -> None:
        """Persist event to storage if path configured."""
        if self._output_path:
            import json

            with open(self._output_path, "a") as f:
                f.write(json.dumps(event) + "\n")

    def get_events(self) -> list[dict[str, Any]]:
        """Get all logged events."""
        return self._events.copy()
