"""Gumi Continuity module (PR06).

Governed Shared Continuity/diary/world-state recall with:
- TTL (Time To Live)
- Recall limits
- Pause
- Burden tracking
- Correction handling

PR06 depends on PR01 (shared_continuity service) and PR04 (admission policy).
"""

from relic.gumi_continuity.types import (
    MarkerStatus,
    FollowupStatus,
    ContinuityMarker,
    ContinuityFollowup,
    ContinuityCorrection,
)

from relic.gumi_continuity.store import (
    GumiContinuityStore,
    get_gumi_continuity_store,
)

from relic.gumi_continuity.admission import (
    ContinuityAdmissionPolicy,
    get_admission_policy,
)

from relic.gumi_continuity.recall import (
    recall_eligible_markers,
    check_recall_eligibility,
    increment_recall_count,
)

from relic.gumi_continuity.events import (
    ContinuityRecallEvent,
    ContinuityAdmissionEvent,
    ContinuityCorrectionEvent,
    ContinuityPauseEvent,
    ContinuityResumeEvent,
)

__all__ = [
    # Types
    "MarkerStatus",
    "FollowupStatus",
    "ContinuityMarker",
    "ContinuityFollowup",
    "ContinuityCorrection",
    # Store
    "GumiContinuityStore",
    "get_gumi_continuity_store",
    # Admission
    "ContinuityAdmissionPolicy",
    "get_admission_policy",
    # Recall
    "recall_eligible_markers",
    "check_recall_eligibility",
    "increment_recall_count",
    # Events
    "ContinuityRecallEvent",
    "ContinuityAdmissionEvent",
    "ContinuityCorrectionEvent",
    "ContinuityPauseEvent",
    "ContinuityResumeEvent",
]
