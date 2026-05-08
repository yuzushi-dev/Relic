"""relic.ui — Researcher audit UI contracts and view models.

This package provides UI-facing data models with zero-knowledge guarantees:
- All view models are redacted by default
- Every visible claim contains lineage_refs and review_status
- UI implements exception-workbench defaults for runtime-impacting items
- UI emits review-burden metrics for evaluation

Key principles:
- Raw final prompts are never persisted
- UI cannot edit compiled artifacts directly
- Feedback does not affect runtime before compiler rerun
- Sensitive marks trigger privacy review
- UI tests do not require cloud provider
- UI traces include actor_role and target_id
- State is not represented through color only
"""

from relic.ui.audit import (
    AuditLogger,
    BatchReleasePolicy,
    ItemState,
    RiskSeverity,
)
from relic.ui.contracts import (
    UI_STATE_DESCRIPTIONS,
    UI_STATE_ENUM,
    ExceptionWorkbenchDefaults,
    FeedbackPropagationTrace,
    LineageRef,
    ResearcherFeedbackEvent,
    ReviewBurdenMetrics,
    ReviewQueueItem,
    ReviewStatus,
    RiskLevel,
)
from relic.ui.feedback import (
    FeedbackProcessor,
    FeedbackPropagationMode,
    ResearcherFeedbackAction,
    SubjectCorrectionSupremacy,
)
from relic.ui.view_models import (
    REDACTED_PLACEHOLDER,
    AuditDashboardViewModel,
    ReviewItemViewModel,
    ReviewQueueViewModel,
    ViewModelBase,
    validate_design,
)

__version__ = "0.1.0"

__all__ = [
    # Contracts
    "LineageRef",
    "ReviewStatus",
    "RiskLevel",
    "ReviewQueueItem",
    "ResearcherFeedbackEvent",
    "FeedbackPropagationTrace",
    "ReviewBurdenMetrics",
    "ExceptionWorkbenchDefaults",
    "UI_STATE_ENUM",
    "UI_STATE_DESCRIPTIONS",
    # View models
    "ViewModelBase",
    "ReviewItemViewModel",
    "ReviewQueueViewModel",
    "AuditDashboardViewModel",
    "REDACTED_PLACEHOLDER",
    "validate_design",
    # Feedback
    "ResearcherFeedbackAction",
    "FeedbackProcessor",
    "SubjectCorrectionSupremacy",
    "FeedbackPropagationMode",
    # Audit
    "AuditLogger",
    "BatchReleasePolicy",
    "ItemState",
    "RiskSeverity",
]
