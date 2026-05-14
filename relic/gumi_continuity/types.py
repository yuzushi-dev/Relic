"""Types for Gumi Continuity (PR06).

Re-exports core types from shared_continuity service for use in
gumi_continuity module. This provides a clean separation of concerns
while maintaining type compatibility.
"""

from relic.shared_continuity.service import (
    MarkerStatus,
    FollowupStatus,
    ContinuityMarker,
    ContinuityFollowup,
    ContinuityCorrection,
    ContinuityServiceError,
    FORBIDDEN_CLINICAL_TERMS,
)

__all__ = [
    "MarkerStatus",
    "FollowupStatus",
    "ContinuityMarker",
    "ContinuityFollowup",
    "ContinuityCorrection",
    "ContinuityServiceError",
    "FORBIDDEN_CLINICAL_TERMS",
]
