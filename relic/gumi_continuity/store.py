"""Gumi Continuity Store (PR06).

Store interface for gumi_continuity module that delegates to the
shared_continuity service. This provides the contract between
the PR06 gumi_continuity module and the PR01/PR04 shared_continuity service.
"""

from typing import Optional, List, Dict, Any

from relic.shared_continuity.service import (
    ContinuityService,
    get_continuity_service as get_shared_continuity_service,
    ContinuityMarker,
    MarkerStatus,
    FollowupStatus,
)


class GumiContinuityStore:
    """Store wrapper for shared_continuity service.
    
    This class provides the interface expected by PR06 while delegating
    to the existing shared_continuity service implementation.
    """

    def __init__(self):
        # Service is resolved per-access (see property below) so the store always
        # binds to the current subject's durable service even if this store was
        # constructed before RELIC_SUBJECT_ID was set in the process.
        pass

    @property
    def _service(self) -> ContinuityService:
        return get_shared_continuity_service()

    def get_marker(self, marker_id: str) -> Optional[Dict[str, Any]]:
        """Get a marker by ID."""
        marker = self._service._markers.get(marker_id)
        if marker is None:
            return None
        return self._sanitize_marker(marker)

    def get_recent_markers(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent markers for a subject."""
        return self._service.recent_markers(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            limit=limit,
        )

    def remember_marker(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        subject_words: List[str],
        source_type: str = "user_confirmed",
        max_recall_count: int = 3,
        ttl_seconds: int = 604800,
        *,
        subject_confirmation: bool,
    ) -> Dict[str, Any]:
        """Create a new subject-confirmed continuity marker.

        subject_confirmation is required (keyword-only): callers must explicitly
        assert the subject confirmed this wording. Inferred/unconfirmed content
        must use propose_candidate() instead.
        """
        return self._service.remember(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            subject_words=subject_words,
            source_type=source_type,
            max_recall_count=max_recall_count,
            ttl_seconds=ttl_seconds,
            subject_confirmation=subject_confirmation,
        )

    def propose_candidate(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        subject_words: List[str],
        source_type: str = "hindsight",
        max_recall_count: int = 3,
        ttl_seconds: int = 604800,
    ) -> Dict[str, Any]:
        """Store an unconfirmed candidate marker (not recalled until confirmed)."""
        return self._service.propose_candidate(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            subject_words=subject_words,
            source_type=source_type,
            max_recall_count=max_recall_count,
            ttl_seconds=ttl_seconds,
        )

    def correct_marker(
        self,
        marker_id: str,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        subject_words: List[str],
        created_by: str = "subject",
    ) -> Dict[str, Any]:
        """Correct an existing marker."""
        return self._service.correct(
            marker_id=marker_id,
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            subject_words=subject_words,
            created_by=created_by,
        )

    def forget_marker(self, marker_id: str, subject_id: str) -> Dict[str, Any]:
        """Remove a marker from Gumi recall."""
        return self._service.forget(marker_id=marker_id, subject_id=subject_id)

    def pause_scope(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pause recall for a scope."""
        return self._service.pause(
            subject_id=subject_id,
            scope_name=scope_name,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
        )

    def resume_scope(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resume recall for a scope."""
        return self._service.resume(
            subject_id=subject_id,
            scope_name=scope_name,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
        )

    def get_due_followups(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get due follow-ups for a subject."""
        return self._service.due_followups(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
        )

    def is_scope_paused(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
        scope_name: str = "global",
    ) -> bool:
        """Check if a scope is paused."""
        scope_key = f"{subject_id}:{gumi_instance_id}:{hermes_profile_id}:{scope_name}"
        return self._service._scopes.get(scope_key, {}).get("is_paused", False)

    def get_descriptive_summary_markers(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get markers eligible for descriptive summaries."""
        return self._service.get_descriptive_summary_markers(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
        )

    def is_marker_recall_eligible(self, marker_id: str) -> bool:
        """Check if a marker is recall-eligible."""
        marker = self._service._markers.get(marker_id)
        if marker is None:
            return False
        return self._service._is_marker_recall_eligible(marker)

    def _sanitize_marker(self, marker: ContinuityMarker) -> Dict[str, Any]:
        """Sanitize marker for output."""
        return self._service._sanitize_output(marker)


# Global store instance
_store: Optional[GumiContinuityStore] = None


def get_gumi_continuity_store() -> GumiContinuityStore:
    """Get the global gumi_continuity store instance."""
    global _store
    if _store is None:
        _store = GumiContinuityStore()
    return _store
