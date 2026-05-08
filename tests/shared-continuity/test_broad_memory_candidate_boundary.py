"""
PR33D — Broad Memory Candidate Boundary Tests

Tests for FIX09: Unconfirmed Hindsight/broad-memory candidates must be marked
candidate_for_confirmation=True and must NOT be returned to Gumi runtime context.
Only confirmed markers can reach Gumi runtime via recent_markers(), due_followups(),
or any Gumi-facing API.
"""

import pytest
from unittest.mock import MagicMock
from relic.shared_continuity.service import (
    ContinuityService,
    ContinuityMarker,
    ContinuityFollowup,
    MarkerStatus,
    FollowupStatus,
)


class TestBroadMemoryCandidateBoundary:
    """Test broad-memory candidate boundary enforcement."""

    def test_unconfirmed_candidate_not_in_gumi_runtime_context(self):
        """
        Unconfirmed broad-memory candidate must NOT appear in recent_markers().
        """
        service = ContinuityService()

        # Create a marker with candidate_for_confirmation=True
        marker = ContinuityMarker(
            marker_id="marker_unconfirmed_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=False,
            source_type="hindsight",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["User mentioned low sleep"],
            gumi_agreed_words=[],
            raw_source_text="User mentioned low sleep.",
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=True,
        )
        service._markers[marker.marker_id] = marker

        # Verify it does NOT appear in recent_markers
        results = service.recent_markers(subject_id="subj_001")
        marker_ids = [r["marker_id"] for r in results]
        assert marker.marker_id not in marker_ids

    def test_confirmed_marker_in_gumi_runtime_context(self):
        """
        Confirmed marker (candidate_for_confirmation=False) must appear in recent_markers().
        """
        service = ContinuityService()

        # Create a confirmed marker
        marker = ContinuityMarker(
            marker_id="marker_confirmed_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["I feel good about this"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=False,
        )
        service._markers[marker.marker_id] = marker

        # Verify it DOES appear in recent_markers
        results = service.recent_markers(subject_id="subj_001")
        marker_ids = [r["marker_id"] for r in results]
        assert marker.marker_id in marker_ids

    def test_candidate_for_confirmation_flag_respected(self):
        """
        is_confirmation_candidate() returns True for candidates.
        """
        service = ContinuityService()

        # Create unconfirmed candidate
        marker = ContinuityMarker(
            marker_id="marker_candidate_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=False,
            source_type="hindsight",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["User mentioned stress"],
            gumi_agreed_words=[],
            raw_source_text="User mentioned stress.",
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=True,
        )
        service._markers[marker.marker_id] = marker

        # is_confirmation_candidate returns True
        assert service.is_confirmation_candidate(marker.marker_id) is True

        # Create confirmed marker
        confirmed_marker = ContinuityMarker(
            marker_id="marker_confirmed_002",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["I confirmed this"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=False,
        )
        service._markers[confirmed_marker.marker_id] = confirmed_marker

        # is_confirmation_candidate returns False for confirmed markers
        assert service.is_confirmation_candidate(confirmed_marker.marker_id) is False

    def test_broad_memory_not_recalled_via_due_followups(self):
        """
        Markers with candidate_for_confirmation=True must NOT appear in due_followups().
        """
        service = ContinuityService()

        # Create a candidate marker
        marker = ContinuityMarker(
            marker_id="marker_followup_candidate_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=False,
            source_type="hindsight",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["User mentioned insomnia"],
            gumi_agreed_words=[],
            raw_source_text="User mentioned insomnia.",
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=True,
        )
        service._markers[marker.marker_id] = marker

        # Create a followup for this marker
        followup = ContinuityFollowup(
            followup_id="followup_001",
            marker_id=marker.marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            max_attempts=3,
            attempt_count=0,
            status=FollowupStatus.DUE,
            followup_interval_seconds=86400,
            next_followup_at="2026-05-09T10:00:00Z",
            ttl_seconds=604800,
            created_at="2026-05-08T10:00:00Z",
            expires_at=None,
            is_paused=False,
            paused_at=None,
            resumed_at=None,
        )
        service._followups[followup.followup_id] = followup

        # Verify the candidate marker does NOT appear in due_followups
        results = service.due_followups(subject_id="subj_001")
        marker_ids = [r["marker_id"] for r in results]
        assert marker.marker_id not in marker_ids

    def test_confirmed_followup_marker_appears_in_due_followups(self):
        """
        Confirmed marker with followup MUST appear in due_followups().
        """
        service = ContinuityService()

        # Create a confirmed marker
        marker = ContinuityMarker(
            marker_id="marker_followup_confirmed_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["I want follow-up on this"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=False,
        )
        service._markers[marker.marker_id] = marker

        # Create a followup for this confirmed marker
        followup = ContinuityFollowup(
            followup_id="followup_002",
            marker_id=marker.marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            max_attempts=3,
            attempt_count=0,
            status=FollowupStatus.DUE,
            followup_interval_seconds=86400,
            next_followup_at="2026-05-09T10:00:00Z",
            ttl_seconds=604800,
            created_at="2026-05-08T10:00:00Z",
            expires_at=None,
            is_paused=False,
            paused_at=None,
            resumed_at=None,
        )
        service._followups[followup.followup_id] = followup

        # Verify the confirmed marker DOES appear in due_followups
        results = service.due_followups(subject_id="subj_001")
        marker_ids = [r["marker_id"] for r in results]
        assert marker.marker_id in marker_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
