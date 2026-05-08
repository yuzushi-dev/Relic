"""UI contracts and data models for researcher audit interface.

This module defines typed dataclasses for the researcher UI with zero-knowledge guarantees:
- All sensitive content is redacted by default
- lineage_refs are required for all visible claims
- review_status tracks item state
- Exception-workbench defaults for runtime-impacting items
- Review-burden metrics for evaluation

Privacy guarantees:
- Raw final prompts are never persisted
- UI cannot edit compiled artifacts directly
- Feedback does not affect runtime before compiler rerun
- Sensitive marks trigger privacy review
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# Placeholder for redacted content - NEVER raw data
REDACTED_PLACEHOLDER = "[REDACTED]"


class ReviewStatus(str, Enum):
    """Review status for UI items.
    
    S0 items require immediate action and cannot be batch-released.
    S1 items require manual review and cannot be batch-released.
    S2 warnings are hidden or batchable only when non-runtime-impacting.
    """
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_RESOLVED = "auto_resolved"
    ESCALATED = "escalated"


class RiskLevel(str, Enum):
    """Risk level for review items.
    
    S0: Hard violation - cannot be batch-released, requires immediate action
    S1: High risk - cannot be batch-released, requires manual review
    S2: Warning - hidden or batchable only when non-runtime-impacting
    """
    S0_HARD_VIOLATION = "s0"
    S1_HIGH_RISK = "s1"
    S2_WARNING = "s2"
    LOW_RISK = "low_risk"


class UI_STATE_ENUM(str, Enum):
    """UI state enumeration for all review items.
    
    States are represented through descriptive text, NOT color only.
    Each state has a corresponding description in UI_STATE_DESCRIPTIONS.
    """
    DISPUTED = "disputed"
    SENSITIVE = "sensitive"
    STALE = "stale"
    UNCERTAIN = "uncertain"
    MISSING_LINEAGE = "missing_lineage"
    RUNTIME_IMPACTING = "runtime_impacting"
    NORMAL = "normal"


# Descriptions for UI states - must be shown to users, NOT color-only representation
UI_STATE_DESCRIPTIONS: dict[UI_STATE_ENUM, str] = {
    UI_STATE_ENUM.DISPUTED: "Content has conflicting claims that require review",
    UI_STATE_ENUM.SENSITIVE: "Privacy-sensitive content detected, triggers privacy review",
    UI_STATE_ENUM.STALE: "Content has not been updated recently and may be outdated",
    UI_STATE_ENUM.UNCERTAIN: "Confidence level is low and requires human validation",
    UI_STATE_ENUM.MISSING_LINEAGE: "Lineage tracking is incomplete for this item",
    UI_STATE_ENUM.RUNTIME_IMPACTING: "Changes to this item affect agent runtime behavior",
    UI_STATE_ENUM.NORMAL: "No issues detected, standard processing applies",
}


class LineageRef(BaseModel):
    """Reference to parent artifacts for lineage tracking.
    
    Every visible claim must contain lineage_refs for audit purposes.
    """
    artifact_id: UUID
    artifact_type: str = Field(description="Type: runtime_profile, agent_embodiment, interaction_policy, etc.")
    relationship: str = Field(description="derived_from, supersedes, references, etc.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    checksum: str | None = Field(default=None, description="SHA-256 checksum for integrity")


class ReviewQueueItem(BaseModel):
    """A single item in the review queue.
    
    All items are redacted by default - only metadata and status are visible.
    Content hash is stored for verification without exposing raw content.
    """
    item_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Redaction by default - content hash for verification
    content_hash: str = Field(description="SHA-256 hash of content for verification")
    is_content_redacted: bool = Field(default=True, description="True if content is redacted")

    # Required: lineage tracking
    lineage_refs: list[LineageRef] = Field(default_factory=list)

    # Required: review status
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING)

    # Risk classification
    risk_level: RiskLevel = Field(default=RiskLevel.LOW_RISK)

    # Runtime impact - S0/S1 cannot be batch-released
    is_runtime_impacting: bool = Field(default=False)

    # Exception workbench flags
    is_disputed: bool = Field(default=False)
    is_sensitive: bool = Field(default=False)
    is_stale: bool = Field(default=False)
    is_uncertain: bool = Field(default=False)
    is_missing_lineage: bool = Field(default=False)

    # Batch release control
    can_batch_release: bool = Field(
        default=False,
        description="False for S0/S1 items, True for S2/non-runtime-impacting only"
    )

    # Review metadata
    assigned_reviewer: str | None = Field(default=None)
    review_notes: str | None = Field(default=None)

    # Actor tracking for audit
    actor_role: str | None = Field(default=None, description="Role of user who created/modified this item")
    target_id: UUID | None = Field(default=None, description="ID of the target artifact")

    def can_auto_resolve(self) -> bool:
        """Check if item can be auto-resolved (low-risk, non-runtime-impacting)."""
        return (
            self.risk_level == RiskLevel.LOW_RISK
            and not self.is_runtime_impacting
            and not self.is_disputed
            and not self.is_sensitive
            and not self.is_uncertain
        )

    def requires_manual_review(self) -> bool:
        """Check if item requires manual review (S0/S1 or disputed/sensitive/uncertain)."""
        return (
            self.risk_level in (RiskLevel.S0_HARD_VIOLATION, RiskLevel.S1_HIGH_RISK)
            or self.is_disputed
            or self.is_sensitive
            or self.is_uncertain
            or self.is_missing_lineage
        )


class ResearcherFeedbackEvent(BaseModel):
    """An event representing researcher feedback on an artifact.
    
    Feedback is tracked for audit but does NOT affect runtime until compiler rerun.
    This prevents feedback from bypassing the correction gate.
    """
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Feedback metadata
    feedback_type: str = Field(
        description="Type: correction, validation, flag, escalation, etc."
    )
    severity: str = Field(description="minor, moderate, major, critical")

    # Target tracking
    target_id: UUID = Field(description="ID of the target artifact")
    actor_role: str = Field(description="Role of researcher providing feedback")

    # Feedback content (can be redacted)
    feedback_content: str = Field(default="")
    is_feedback_redacted: bool = Field(default=True)
    feedback_content_hash: str | None = Field(default=None)

    # Lineage tracking
    lineage_refs: list[LineageRef] = Field(default_factory=list)

    # Status
    applied: bool = Field(default=False, description="True only after compiler rerun")
    applied_at: datetime | None = Field(default=None)

    # Privacy trigger
    triggered_privacy_review: bool = Field(default=False)

    # Subject user override protection
    subject_user_correction_respected: bool = Field(
        default=True,
        description="True if researcher validation did NOT override subject_user correction"
    )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the feedback event.
        
        Returns (is_valid, error_messages).
        """
        errors = []

        # Verify lineage refs exist
        if not self.lineage_refs:
            errors.append("feedback_requires_lineage_refs")

        # Verify actor_role is present
        if not self.actor_role:
            errors.append("feedback_requires_actor_role")

        # Verify target_id is present
        if not self.target_id:
            errors.append("feedback_requires_target_id")

        # Verify researcher didn't override subject_user correction
        if not self.subject_user_correction_respected:
            errors.append("researcher_validation_override_blocked")

        return len(errors) == 0, errors


class FeedbackPropagationTrace(BaseModel):
    """Trace of feedback propagation through the system.
    
    Tracks how feedback moves through correction gate, compiler, and audit.
    """
    trace_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Source event
    source_event: ResearcherFeedbackEvent

    # Propagation stages
    stages: list[FeedbackStage] = Field(default_factory=list)

    # Audit metadata
    total_stages_completed: int = 0
    completed: bool = Field(default=False)

    # Error tracking
    errors: list[str] = Field(default_factory=list)


class FeedbackStage(BaseModel):
    """A single stage in feedback propagation."""
    stage_name: str = Field(description="correction_gate, compiler, audit, etc.")
    entered_at: datetime = Field(default_factory=datetime.utcnow)
    exited_at: datetime | None = Field(default=None)
    outcome: str = Field(description="accepted, rejected, pending, error")
    details: str | None = Field(default=None)


class ReviewBurdenMetrics(BaseModel):
    """Metrics for review burden tracking and evaluation.
    
    These metrics are emitted by UI for evaluation fixtures.
    """
    # Timing metrics
    total_items: int = Field(default=0)
    items_reviewed: int = Field(default=0)

    # Manual review rate
    manual_review_rate: float = Field(
        default=0.0,
        description="Proportion of items requiring manual review"
    )

    # Time metrics
    median_review_time_per_item: float = Field(
        default=0.0,
        description="Median time in seconds to review one item"
    )
    total_review_time_seconds: float = Field(default=0.0)

    # Queue health
    high_risk_queue_age: float = Field(
        default=0.0,
        description="Time in seconds since oldest high-risk item was added"
    )

    # Resolution metrics
    auto_resolved_low_risk_rate: float = Field(
        default=0.0,
        description="Proportion of low-risk items auto-resolved without manual review"
    )

    # Risk distribution
    s0_count: int = Field(default=0)
    s1_count: int = Field(default=0)
    s2_count: int = Field(default=0)
    low_risk_count: int = Field(default=0)

    # Batch statistics
    batch_release_count: int = Field(default=0)
    batch_release_blocked_s0_s1: int = Field(default=0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON output."""
        return {
            "total_items": self.total_items,
            "items_reviewed": self.items_reviewed,
            "manual_review_rate": self.manual_review_rate,
            "median_review_time_per_item": self.median_review_time_per_item,
            "total_review_time_seconds": self.total_review_time_seconds,
            "high_risk_queue_age": self.high_risk_queue_age,
            "auto_resolved_low_risk_rate": self.auto_resolved_low_risk_rate,
            "s0_count": self.s0_count,
            "s1_count": self.s1_count,
            "s2_count": self.s2_count,
            "low_risk_count": self.low_risk_count,
            "batch_release_count": self.batch_release_count,
            "batch_release_blocked_s0_s1": self.batch_release_blocked_s0_s1,
        }


class ExceptionWorkbenchDefaults(BaseModel):
    """Default exception-workbench configuration for runtime-impacting items.
    
    These defaults ensure consistent handling of items that affect runtime behavior:
    - disputed: Items with conflicting claims
    - sensitive: Items with privacy-sensitive content
    - stale: Items that haven't been updated recently
    - uncertain: Items with low confidence
    - missing_lineage: Items without complete lineage tracking
    """
    # Default review status for each exception type
    default_review_status: dict[str, ReviewStatus] = Field(default_factory=lambda: {
        "disputed": ReviewStatus.PENDING,
        "sensitive": ReviewStatus.PENDING,
        "stale": ReviewStatus.UNDER_REVIEW,
        "uncertain": ReviewStatus.UNDER_REVIEW,
        "missing_lineage": ReviewStatus.PENDING,
    })

    # Default risk level for each exception type
    default_risk_level: dict[str, RiskLevel] = Field(default_factory=lambda: {
        "disputed": RiskLevel.S1_HIGH_RISK,
        "sensitive": RiskLevel.S1_HIGH_RISK,
        "stale": RiskLevel.S2_WARNING,
        "uncertain": RiskLevel.S1_HIGH_RISK,
        "missing_lineage": RiskLevel.S2_WARNING,
    })

    # Batch release rules
    can_batch_release: dict[str, bool] = Field(default_factory=lambda: {
        "disputed": False,
        "sensitive": False,
        "stale": True,  # Only when non-runtime-impacting
        "uncertain": False,
        "missing_lineage": True,  # Only when non-runtime-impacting
    })

    # Runtime impact override
    runtime_impacting_override: dict[str, bool] = Field(default_factory=lambda: {
        "disputed": True,
        "sensitive": True,
        "stale": False,
        "uncertain": True,
        "missing_lineage": False,
    })

    @classmethod
    def for_item(cls, item: ReviewQueueItem) -> ReviewQueueItem:
        """Apply exception-workbench defaults to a review queue item.
        
        Returns a new item with defaults applied based on exception flags.
        """
        defaults = cls()

        # Apply default risk level based on exception type
        if item.is_disputed:
            item.risk_level = defaults.default_risk_level["disputed"]
            item.can_batch_release = defaults.can_batch_release["disputed"]
        if item.is_sensitive:
            item.risk_level = defaults.default_risk_level["sensitive"]
            item.can_batch_release = defaults.can_batch_release["sensitive"]
            item.review_status = ReviewStatus.ESCALATED  # Trigger privacy review
        if item.is_stale:
            item.risk_level = defaults.default_risk_level["stale"]
            if not item.is_runtime_impacting:
                item.can_batch_release = defaults.can_batch_release["stale"]
        if item.is_uncertain:
            item.risk_level = defaults.default_risk_level["uncertain"]
            item.can_batch_release = defaults.can_batch_release["uncertain"]
        if item.is_missing_lineage:
            item.risk_level = defaults.default_risk_level["missing_lineage"]
            if not item.is_runtime_impacting:
                item.can_batch_release = defaults.can_batch_release["missing_lineage"]

        # S0/S1 items cannot be batch-released
        if item.risk_level in (RiskLevel.S0_HARD_VIOLATION, RiskLevel.S1_HIGH_RISK):
            item.can_batch_release = False
        # S2 items can batch only when non-runtime-impacting
        elif item.risk_level == RiskLevel.S2_WARNING and not item.is_runtime_impacting:
            item.can_batch_release = True

        return item
