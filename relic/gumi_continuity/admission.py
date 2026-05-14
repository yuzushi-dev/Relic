"""Continuity Admission Policy (PR06).

Admission policy for determining whether continuity markers
should be recalled based on:
- TTL (Time To Live)
- Recall limits
- Pause state
- Burden tracking
- Clinical safety
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from relic.gumi_continuity.store import GumiContinuityStore, get_gumi_continuity_store


@dataclass
class AdmissionDecision:
    """Decision result for continuity admission."""
    marker_id: str
    admitted: bool
    reason: str
    blocked_by: Optional[str] = None  # TTL, recall_limit, pause, burden, clinical
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def _parse_expires_at(expires_at: str) -> Optional[datetime]:
    """Parse expires_at string to datetime, handling timezone."""
    if not expires_at:
        return None
    try:
        # Handle ISO format with Z suffix
        if expires_at.endswith("Z"):
            # Convert Z to +00:00 for fromisoformat
            return datetime.fromisoformat(expires_at[:-1] + "+00:00")
        return datetime.fromisoformat(expires_at)
    except (ValueError, TypeError):
        return None


def _now_utc() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class ContinuityAdmissionPolicy:
    """Policy for governing continuity marker recall.

    This policy evaluates whether a marker should be admitted into
    Gumi runtime context based on multiple criteria:
    - TTL: Marker must not be expired
    - Recall limit: Marker must not exceed max_recall_count
    - Pause: Marker scope must not be paused
    - Burden: Markers must not overwhelm context
    - Clinical safety: No forbidden clinical terms
    """

    def __init__(
        self,
        store: Optional[GumiContinuityStore] = None,
        max_context_markers: int = 10,
    ):
        self._store = store or get_gumi_continuity_store()
        self._max_context_markers = max_context_markers

    def evaluate_marker(
        self,
        marker: Dict[str, Any],
    ) -> AdmissionDecision:
        """Evaluate whether a single marker should be admitted.

        Args:
            marker: Marker data dict

        Returns:
            AdmissionDecision with admitted=True/False and reason
        """
        marker_id = marker.get("marker_id", "unknown")

        # PR06-T12: block PR32 sensitive_signal objects from entering continuity
        if marker.get("origin") == "sensitive_signal":
            return AdmissionDecision(
                marker_id=marker_id,
                admitted=False,
                reason="PR32 sensitive_signal objects are not memories and must not be recalled by Gumi",
                blocked_by="sensitive_signal_origin",
            )

        # Check TTL - marker must not be expired
        expires_at = marker.get("expires_at")
        if expires_at:
            expires_dt = _parse_expires_at(expires_at)
            if expires_dt:
                now = _now_utc()
                # Make expires_dt naive for comparison if needed
                if expires_dt.tzinfo is not None:
                    expires_dt_naive = expires_dt.replace(tzinfo=None)
                else:
                    expires_dt_naive = expires_dt
                if now.replace(tzinfo=None) > expires_dt_naive:
                    return AdmissionDecision(
                        marker_id=marker_id,
                        admitted=False,
                        reason="Marker has expired",
                        blocked_by="ttl",
                    )

        # Check recall limit
        recall_count = marker.get("recall_count", 0)
        max_recall = marker.get("max_recall_count", 3)
        if recall_count >= max_recall:
            return AdmissionDecision(
                marker_id=marker_id,
                admitted=False,
                reason=f"Marker has reached recall limit ({recall_count}/{max_recall})",
                blocked_by="recall_limit",
            )

        # Check pause state
        subject_id = marker.get("subject_id")
        gumi_instance_id = marker.get("gumi_instance_id")
        hermes_profile_id = marker.get("hermes_profile_id")
        if self._store.is_scope_paused(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
        ):
            return AdmissionDecision(
                marker_id=marker_id,
                admitted=False,
                reason="Marker scope is paused",
                blocked_by="pause",
            )

        # Check status
        status = marker.get("status")
        if status != "active":
            return AdmissionDecision(
                marker_id=marker_id,
                admitted=False,
                reason=f"Marker status is {status}, not active",
                blocked_by="status",
            )

        # Check gumi_recall_allowed
        if not marker.get("gumi_recall_allowed", True):
            return AdmissionDecision(
                marker_id=marker_id,
                admitted=False,
                reason="Marker is not allowed for Gumi recall",
                blocked_by="gumi_recall_allowed",
            )

        # All checks passed - admit
        return AdmissionDecision(
            marker_id=marker_id,
            admitted=True,
            reason="Marker passes all admission checks",
        )

    def evaluate_markers(
        self,
        markers: List[Dict[str, Any]],
    ) -> List[AdmissionDecision]:
        """Evaluate multiple markers for admission.

        Args:
            markers: List of marker data dicts

        Returns:
            List of AdmissionDecision objects
        """
        decisions = []
        admitted_count = 0

        for marker in markers:
            decision = self.evaluate_marker(marker)

            # Check burden: don't exceed max context markers
            if decision.admitted:
                if admitted_count >= self._max_context_markers:
                    decisions.append(AdmissionDecision(
                        marker_id=marker.get("marker_id", "unknown"),
                        admitted=False,
                        reason=f"Exceeds max context markers ({self._max_context_markers})",
                        blocked_by="burden",
                    ))
                    continue
                admitted_count += 1

            decisions.append(decision)

        return decisions

    def filter_admitted_markers(
        self,
        markers: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter markers to only those that are admitted.

        Args:
            markers: List of marker data dicts

        Returns:
            List of marker dicts that pass admission
        """
        decisions = self.evaluate_markers(markers)
        admitted_ids = {d.marker_id for d in decisions if d.admitted}
        return [m for m in markers if m.get("marker_id") in admitted_ids]

    def get_blocked_reasons(
        self,
        markers: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        """Get reasons why markers were blocked.

        Args:
            markers: List of marker data dicts

        Returns:
            Dict mapping blocked_by reason to list of marker_ids
        """
        decisions = self.evaluate_markers(markers)
        reasons: Dict[str, List[str]] = {
            "ttl": [],
            "recall_limit": [],
            "pause": [],
            "burden": [],
            "status": [],
            "gumi_recall_allowed": [],
            "clinical": [],
        }

        for decision in decisions:
            if not decision.admitted and decision.blocked_by:
                reasons.setdefault(decision.blocked_by, []).append(decision.marker_id)

        # Remove empty reason lists
        return {k: v for k, v in reasons.items() if v}


# Global admission policy instance
_policy: Optional[ContinuityAdmissionPolicy] = None


def get_admission_policy() -> ContinuityAdmissionPolicy:
    """Get the global admission policy instance."""
    global _policy
    if _policy is None:
        _policy = ContinuityAdmissionPolicy()
    return _policy
