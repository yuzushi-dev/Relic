"""Recall Logic for Gumi Continuity (PR06).

Provides recall functions for determining which markers
should be recalled based on admission policy criteria.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from relic.gumi_continuity.store import GumiContinuityStore, get_gumi_continuity_store
from relic.gumi_continuity.admission import ContinuityAdmissionPolicy, get_admission_policy


def recall_eligible_markers(
    subject_id: str,
    gumi_instance_id: Optional[str] = None,
    hermes_profile_id: Optional[str] = None,
    store: Optional[GumiContinuityStore] = None,
    admission_policy: Optional[ContinuityAdmissionPolicy] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Get recall-eligible markers for a subject.

    This function returns markers that pass all admission checks:
    - TTL not expired
    - Recall limit not exceeded
    - Scope not paused
    - Status is active
    - Gumi recall is allowed

    Args:
        subject_id: Subject identifier
        gumi_instance_id: Optional Gumi instance ID
        hermes_profile_id: Optional Hermes profile ID
        store: Optional store instance (uses global if not provided)
        admission_policy: Optional admission policy (uses global if not provided)
        limit: Maximum number of markers to return

    Returns:
        List of recall-eligible marker dicts
    """
    store = store or get_gumi_continuity_store()
    admission_policy = admission_policy or get_admission_policy()

    # Get recent markers from store (already filtered by shared_continuity service)
    markers = store.get_recent_markers(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        limit=limit * 2,  # Get more to account for burden filtering
    )

    # Apply admission policy to filter
    admitted_markers = admission_policy.filter_admitted_markers(markers)

    # Apply limit
    return admitted_markers[:limit]


def check_recall_eligibility(
    marker_id: str,
    store: Optional[Any] = None,
) -> Dict[str, Any]:
    """Check if a specific marker is recall-eligible.

    Args:
        marker_id: Marker identifier
        store: Optional store instance (GumiContinuityStore or ContinuityService)

    Returns:
        Dict with eligible (bool) and reason (str)
    """
    # Get the marker from either store type
    if store is None:
        from relic.gumi_continuity.store import get_gumi_continuity_store
        store = get_gumi_continuity_store()

    # Handle both GumiContinuityStore and ContinuityService
    if hasattr(store, 'get_marker'):
        marker = store.get_marker(marker_id)
    elif hasattr(store, '_markers'):
        # It's a ContinuityService
        marker_dict = store._markers.get(marker_id)
        marker = marker_dict if marker_dict else None
    else:
        return {
            "eligible": False,
            "reason": "Invalid store type",
            "marker_id": marker_id,
        }

    if marker is None:
        return {
            "eligible": False,
            "reason": "Marker not found",
            "marker_id": marker_id,
        }

    # Convert to dict if needed
    if hasattr(marker, '__dict__'):
        marker = vars(marker)

    # Check eligibility using the store's is_marker_recall_eligible method
    if hasattr(store, 'is_marker_recall_eligible'):
        is_eligible = store.is_marker_recall_eligible(marker_id)
    elif hasattr(store, '_is_marker_recall_eligible'):
        # It's a ContinuityService - get the marker object
        marker_obj = store._markers.get(marker_id)
        is_eligible = store._is_marker_recall_eligible(marker_obj) if marker_obj else False
    else:
        is_eligible = False

    if not is_eligible:
        # Determine reason
        status = marker.get("status")
        if status and status != "active":
            reason = f"Marker status is {status}"
        elif not marker.get("gumi_recall_allowed", True):
            reason = "Marker not allowed for Gumi recall"
        elif marker.get("recall_count", 0) >= marker.get("max_recall_count", 3):
            reason = "Marker has reached recall limit"
        elif marker.get("expires_at"):
            try:
                expires_at = marker["expires_at"]
                if expires_at:
                    expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > expires_dt:
                        reason = "Marker has expired"
                    else:
                        reason = "Unknown reason"
                else:
                    reason = "Unknown reason"
            except (ValueError, TypeError):
                reason = "Unknown reason"
        else:
            reason = "Unknown reason"
    else:
        reason = "Marker passes all eligibility checks"

    return {
        "eligible": is_eligible,
        "reason": reason,
        "marker_id": marker_id,
        "recall_count": marker.get("recall_count", 0),
        "max_recall_count": marker.get("max_recall_count", 3),
        "status": marker.get("status"),
        "gumi_recall_allowed": marker.get("gumi_recall_allowed", True),
        "expires_at": marker.get("expires_at"),
    }


def increment_recall_count(
    marker_id: str,
    store: Optional[Any] = None,
) -> Dict[str, Any]:
    """Increment the recall count for a marker.

    Args:
        marker_id: Marker identifier
        store: Optional store instance

    Returns:
        Dict with success (bool) and new recall_count
    """
    # Get the underlying service to access _markers
    from relic.shared_continuity.service import get_continuity_service
    service = get_continuity_service()

    marker = service._markers.get(marker_id)
    if marker is None:
        return {
            "success": False,
            "reason": "Marker not found",
            "marker_id": marker_id,
        }

    marker.recall_count += 1
    marker.updated_at = datetime.now().isoformat() + "Z"

    return {
        "success": True,
        "marker_id": marker_id,
        "recall_count": marker.recall_count,
        "max_recall_count": marker.max_recall_count,
    }
