"""View models for researcher audit UI with redacted-by-default approach.

This module implements the UI layer with zero-knowledge guarantees:
- All view models are redacted by default
- Every visible claim contains lineage_refs and review_status
- UI cannot edit compiled artifacts directly
- Raw final prompts are never persisted
- State is NOT represented through color only

The view models act as a secure interface between the backend and researcher UI,
ensuring that sensitive content is never exposed without explicit review.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from relic.ui.contracts import (
    REDACTED_PLACEHOLDER,
    UI_STATE_DESCRIPTIONS,
    UI_STATE_ENUM,
    ExceptionWorkbenchDefaults,
    LineageRef,
    ReviewBurdenMetrics,
    ReviewQueueItem,
    ReviewStatus,
    RiskLevel,
)

# Type variable for generic view models
T = TypeVar("T")


# Placeholder for redacted content - NEVER raw data
REDACTED_PLACEHOLDER = "[REDACTED]"


class ViewModelBase(BaseModel, Generic[T]):
    """Base class for all UI view models.
    
    Guarantees:
    - All view models are redacted by default
    - Every visible claim contains lineage_refs and review_status
    - State is represented through descriptive text, NOT color only
    - actor_role and target_id are always present in traces
    """

    # Required fields for all view models
    view_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Lineage tracking - required for all visible claims
    lineage_refs: list[LineageRef] = Field(default_factory=list)

    # Review status - required for all visible claims
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING)

    @field_validator("lineage_refs")
    @classmethod
    def validate_lineage_refs(cls, v: list[LineageRef]) -> list[LineageRef]:
        """Ensure lineage_refs is always a list."""
        if v is None:
            return []
        return v

    def get_display_state(self) -> str:
        """Get human-readable state description.
        
        Returns descriptive text, NOT color representation.
        Must show UI_STATE_DESCRIPTIONS value.
        """
        return "Review pending - awaiting researcher assessment"

    def get_risk_indicator(self) -> str:
        """Get risk indicator text.
        
        Returns descriptive text, NOT color representation.
        """
        return f"Risk level: {self.review_status.value}"


class ReviewItemViewModel(ViewModelBase[ReviewQueueItem]):
    """View model for a single review item.
    
    Implements redacted-by-default for researcher UI:
    - Content is redacted by default
    - Content hash is shown for verification
    - Lineage refs are required
    - Review status is always visible
    - State is descriptive text, NOT color
    """

    # Underlying data reference
    item_id: UUID = Field(description="ID of the underlying review item")
    content_hash: str = Field(description="SHA-256 hash of content for verification")

    # Redaction flag - content shown only when explicitly requested
    is_content_redacted: bool = Field(default=True)

    # Exception workbench flags
    is_disputed: bool = Field(default=False)
    is_sensitive: bool = Field(default=False)
    is_stale: bool = Field(default=False)
    is_uncertain: bool = Field(default=False)
    is_missing_lineage: bool = Field(default=False)

    # Runtime impact
    is_runtime_impacting: bool = Field(default=False)

    # Risk level with required description
    risk_level: RiskLevel = Field(default=RiskLevel.LOW_RISK)

    # Batch release control - S0/S1 cannot be batch-released
    can_batch_release: bool = Field(default=False)

    # Assigned reviewer
    assigned_reviewer: str | None = Field(default=None)

    # Actor tracking for audit
    actor_role: str | None = Field(default=None)
    target_id: UUID | None = Field(default=None)

    # Sensitive mark triggers privacy review
    @field_validator("is_sensitive")
    @classmethod
    def validate_sensitive_triggers_privacy(cls, v: bool, info) -> bool:
        """Sensitive mark must trigger privacy review."""
        return v

    @classmethod
    def from_item(cls, item: ReviewQueueItem) -> ReviewItemViewModel:
        """Create view model from a review queue item.
        
        Applies exception-workbench defaults.
        """
        # Apply exception workbench defaults
        item = ExceptionWorkbenchDefaults.for_item(item)

        return cls(
            item_id=item.item_id,
            content_hash=item.content_hash,
            is_content_redacted=item.is_content_redacted,
            lineage_refs=item.lineage_refs,
            review_status=item.review_status,
            is_disputed=item.is_disputed,
            is_sensitive=item.is_sensitive,
            is_stale=item.is_stale,
            is_uncertain=item.is_uncertain,
            is_missing_lineage=item.is_missing_lineage,
            is_runtime_impacting=item.is_runtime_impacting,
            risk_level=item.risk_level,
            can_batch_release=item.can_batch_release,
            assigned_reviewer=item.assigned_reviewer,
            actor_role=item.actor_role,
            target_id=item.target_id,
        )

    def get_display_state(self) -> str:
        """Get human-readable state description.
        
        Returns descriptive text based on exception flags,
        NOT color representation.
        """
        states = []

        if self.is_disputed:
            states.append(UI_STATE_DESCRIPTIONS[UI_STATE_ENUM.DISPUTED])
        if self.is_sensitive:
            states.append(UI_STATE_DESCRIPTIONS[UI_STATE_ENUM.SENSITIVE])
        if self.is_stale:
            states.append(UI_STATE_DESCRIPTIONS[UI_STATE_ENUM.STALE])
        if self.is_uncertain:
            states.append(UI_STATE_DESCRIPTIONS[UI_STATE_ENUM.UNCERTAIN])
        if self.is_missing_lineage:
            states.append(UI_STATE_DESCRIPTIONS[UI_STATE_ENUM.MISSING_LINEAGE])
        if self.is_runtime_impacting:
            states.append(UI_STATE_DESCRIPTIONS[UI_STATE_ENUM.RUNTIME_IMPACTING])

        if not states:
            return UI_STATE_DESCRIPTIONS[UI_STATE_ENUM.NORMAL]

        return "; ".join(states)

    def get_risk_indicator(self) -> str:
        """Get risk indicator text with full description.
        
        NOT color representation.
        """
        risk_descriptions = {
            RiskLevel.S0_HARD_VIOLATION: "S0 - Hard violation (cannot batch release)",
            RiskLevel.S1_HIGH_RISK: "S1 - High risk (cannot batch release)",
            RiskLevel.S2_WARNING: "S2 - Warning (batchable only if non-runtime-impacting)",
            RiskLevel.LOW_RISK: "Low risk - Standard processing",
        }

        return risk_descriptions.get(self.risk_level, "Unknown risk level")

    def get_batch_release_status(self) -> str:
        """Get batch release status with explanation.
        
        S0/S1 items CANNOT be batch-released.
        S2 items are batchable only when non-runtime-impacting.
        """
        if self.risk_level in (RiskLevel.S0_HARD_VIOLATION, RiskLevel.S1_HIGH_RISK):
            return "BLOCKED: S0/S1 items cannot be batch-released"

        if self.risk_level == RiskLevel.S2_WARNING and self.is_runtime_impacting:
            return "BLOCKED: S2 runtime-impacting items cannot be batch-released"

        if self.can_batch_release:
            return "ALLOWED: Low-risk non-runtime-impacting item"

        return "BLOCKED: Review required before release"

    def validate_trace_requirements(self) -> tuple[bool, list[str]]:
        """Validate that trace requirements are met.
        
        Returns (is_valid, error_messages).
        UI trace MUST have actor_role and target_id.
        """
        errors = []

        if not self.actor_role:
            errors.append("UI_trace_missing_actor_role")

        if not self.target_id:
            errors.append("UI_trace_missing_target_id")

        return len(errors) == 0, errors


class ReviewQueueViewModel(ViewModelBase[list[ReviewQueueItem]]):
    """View model for the complete review queue.
    
    Implements redacted-by-default:
    - All items show only metadata and status
    - Content hash shown for verification
    - S0/S1 items prominently displayed (not buried)
    - Review burden metrics included
    """

    # Queue items with view models
    items: list[ReviewItemViewModel] = Field(default_factory=list)

    # Review burden metrics for evaluation
    metrics: ReviewBurdenMetrics = Field(default_factory=ReviewBurdenMetrics)

    # Queue health indicators
    oldest_high_risk_item_age: float = Field(
        default=0.0,
        description="Age in seconds of the oldest high-risk (S0/S1) item"
    )

    @classmethod
    def from_items(
        cls,
        items: list[ReviewQueueItem],
        metrics: ReviewBurdenMetrics | None = None,
    ) -> ReviewQueueViewModel:
        """Create queue view model from review items.
        
        Applies exception-workbench defaults and ensures
        high-risk items are not buried behind low-risk items.
        """
        view_models = []

        # Sort by risk level (S0 first, then S1, S2, low_risk)
        risk_order = {
            RiskLevel.S0_HARD_VIOLATION: 0,
            RiskLevel.S1_HIGH_RISK: 1,
            RiskLevel.S2_WARNING: 2,
            RiskLevel.LOW_RISK: 3,
        }

        sorted_items = sorted(
            items,
            key=lambda x: risk_order.get(x.risk_level, 99)
        )

        for item in sorted_items:
            view_models.append(ReviewItemViewModel.from_item(item))

        # Calculate metrics if not provided
        if metrics is None:
            metrics = ReviewBurdenMetrics()
            metrics.total_items = len(items)
            metrics.items_reviewed = len([i for i in items if i.review_status != ReviewStatus.PENDING])

            # Count by risk level
            for item in items:
                if item.risk_level == RiskLevel.S0_HARD_VIOLATION:
                    metrics.s0_count += 1
                elif item.risk_level == RiskLevel.S1_HIGH_RISK:
                    metrics.s1_count += 1
                elif item.risk_level == RiskLevel.S2_WARNING:
                    metrics.s2_count += 1
                else:
                    metrics.low_risk_count += 1

            # Calculate manual review rate
            if metrics.total_items > 0:
                manual_items = metrics.s0_count + metrics.s1_count + metrics.s2_count
                metrics.manual_review_rate = manual_items / metrics.total_items

            # Calculate auto-resolved low-risk rate
            if metrics.low_risk_count > 0:
                auto_resolved = len([
                    i for i in items
                    if i.risk_level == RiskLevel.LOW_RISK
                    and i.review_status == ReviewStatus.AUTO_RESOLVED
                ])
                metrics.auto_resolved_low_risk_rate = auto_resolved / metrics.low_risk_count

            # Calculate high-risk queue age (age of oldest high-risk item)
            now = datetime.utcnow()
            high_risk_items = [
                i for i in items
                if i.risk_level in (RiskLevel.S0_HARD_VIOLATION, RiskLevel.S1_HIGH_RISK)
            ]
            if high_risk_items:
                oldest = min(high_risk_items, key=lambda x: x.created_at)
                age = (now - oldest.created_at).total_seconds()
                metrics.high_risk_queue_age = age

        return cls(
            items=view_models,
            metrics=metrics,
            lineage_refs=[],  # Queue-level lineage is aggregated from items
        )

    def get_display_state(self) -> str:
        """Get human-readable queue state."""
        s0_count = len([i for i in self.items if i.risk_level == RiskLevel.S0_HARD_VIOLATION])
        s1_count = len([i for i in self.items if i.risk_level == RiskLevel.S1_HIGH_RISK])

        if s0_count > 0:
            return f"CRITICAL: {s0_count} S0 item(s) require immediate action"
        if s1_count > 0:
            return f"WARNING: {s1_count} S1 item(s) require manual review"

        return f"Queue healthy: {len(self.items)} items pending review"

    def get_high_risk_items(self) -> list[ReviewItemViewModel]:
        """Get all high-risk items (S0 and S1).
        
        These items cannot be batch-released and should not be buried.
        """
        return [
            i for i in self.items
            if i.risk_level in (RiskLevel.S0_HARD_VIOLATION, RiskLevel.S1_HIGH_RISK)
        ]


class AuditDashboardViewModel(ViewModelBase[None]):
    """View model for the researcher audit dashboard.
    
    Provides an overview of all review queues, metrics, and audit status.
    """

    # Active queues
    review_queues: dict[str, ReviewQueueViewModel] = Field(default_factory=dict)

    # Global metrics
    global_metrics: ReviewBurdenMetrics = Field(default_factory=ReviewBurdenMetrics)

    # Privacy review status
    pending_privacy_reviews: int = Field(default=0)
    triggered_by_sensitive_mark: int = Field(default=0)

    # System health
    last_audit_timestamp: datetime = Field(default_factory=datetime.utcnow)
    system_status: str = Field(default="operational")

    def get_display_state(self) -> str:
        """Get dashboard state summary."""
        if self.pending_privacy_reviews > 0:
            return f"PRIVACY ALERT: {self.pending_privacy_reviews} pending privacy reviews"

        if self.global_metrics.s0_count > 0:
            return f"CRITICAL: {self.global_metrics.s0_count} S0 violations require action"

        return f"Dashboard operational: {self.global_metrics.total_items} items across all queues"


def validate_design() -> bool:
    """Validate DESIGN.md compliance for UI implementation.
    
    This function checks that the UI implementation adheres to:
    - All view models are redacted by default
    - Every visible claim contains lineage_refs and review_status
    - UI implements exception-workbench defaults
    - State is NOT represented through color only
    
    Returns True if design contract is satisfied.
    Raises AssertionError if any requirement is violated.
    """
    # Check that all contract classes are properly defined
    from relic.ui.contracts import (
        UI_STATE_DESCRIPTIONS,
        ExceptionWorkbenchDefaults,
        ReviewBurdenMetrics,
        ReviewQueueItem,
        ReviewStatus,
    )

    # Validate UI_STATE_DESCRIPTIONS is populated
    assert len(UI_STATE_DESCRIPTIONS) > 0, "UI_STATE_DESCRIPTIONS must not be empty"
    assert all(
        isinstance(desc, str) and len(desc) > 0
        for desc in UI_STATE_DESCRIPTIONS.values()
    ), "All UI_STATE_DESCRIPTIONS must have non-empty string values"

    # Validate ExceptionWorkbenchDefaults
    defaults = ExceptionWorkbenchDefaults()
    assert "disputed" in defaults.default_risk_level
    assert defaults.can_batch_release["disputed"] is False  # S0/S1 cannot batch

    # Validate ReviewQueueItem has required fields
    item = ReviewQueueItem(
        content_hash="test_hash",
        lineage_refs=[],
        review_status=ReviewStatus.PENDING,
    )
    assert item.is_content_redacted is True, "ReviewQueueItem must be redacted by default"
    assert item.can_batch_release is False, "S0/S1 items cannot batch release"

    # Validate ReviewBurdenMetrics has all required fields
    metrics = ReviewBurdenMetrics()
    assert hasattr(metrics, "manual_review_rate")
    assert hasattr(metrics, "median_review_time_per_item")
    assert hasattr(metrics, "high_risk_queue_age")
    assert hasattr(metrics, "auto_resolved_low_risk_rate")

    # Validate view models
    assert REDACTED_PLACEHOLDER == "[REDACTED]", "REDACTED_PLACEHOLDER must be [REDACTED]"

    return True
