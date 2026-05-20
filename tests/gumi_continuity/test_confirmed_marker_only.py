"""
PR06 — Test that only confirmed markers are admitted for Gumi recall.

Tests for FIX01: Only subject-confirmed markers are admitted into
Gumi runtime context. Unconfirmed candidates are blocked.
"""

import pytest
from datetime import datetime, timedelta

from relic.gumi_continuity import (
    GumiContinuityStore,
    ContinuityAdmissionPolicy,
    get_gumi_continuity_store,
    get_admission_policy,
)
from relic.shared_continuity.service import (
    ContinuityService,
    ContinuityMarker,
    MarkerStatus,
)


@pytest.fixture
def store():
    """Fresh store for each test."""
    return GumiContinuityStore()


@pytest.fixture
def admission_policy():
    """Fresh admission policy for each test."""
    return ContinuityAdmissionPolicy()


@pytest.fixture
def service():
    """Fresh service for direct marker manipulation."""
    return ContinuityService()


class TestConfirmedMarkerOnly:
    """Test that only confirmed markers are admitted."""

    def test_confirmed_marker_admitted(self, store, admission_policy):
        """Confirmed marker is admitted for Gumi recall."""
        # Create a confirmed marker
        marker = store.remember_marker(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["confirmed marker"],
            subject_confirmation=True,
        )

        assert marker["subject_confirmation"] is True

        # Verify it's recalled
        recent = store.get_recent_markers(subject_id="subj_001")
        assert len(recent) >= 1
        assert any(m["marker_id"] == marker["marker_id"] for m in recent)

    def test_unconfirmed_marker_not_admitted(self, service, admission_policy):
        """Unconfirmed marker is NOT admitted for Gumi recall."""
        # Create an unconfirmed marker directly
        marker_id = f"unconfirmed_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=False,  # Not confirmed
            source_type="hindsight",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["unconfirmed marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        # The service's recent_markers should NOT return it
        # because subject_confirmation is False
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id not in marker_ids

    def test_candidate_for_confirmation_not_admitted(self, service, admission_policy):
        """Marker with candidate_for_confirmation=True is NOT admitted."""
        # Create a candidate marker directly
        marker_id = f"candidate_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="hindsight",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["candidate marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at=datetime.now().isoformat() + "Z",
            candidate_for_confirmation=True,  # Pending confirmation
        )
        service._markers[marker_id] = marker

        # The service's recent_markers should NOT return it
        # because candidate_for_confirmation is True
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id not in marker_ids

    def test_mixed_confirmed_and_unconfirmed_markers(self, store, service):
        """Mixed confirmed/unconfirmed markers - only confirmed returned."""
        # Create confirmed marker
        confirmed = store.remember_marker(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["confirmed"],
            subject_confirmation=True,
        )

        # Create unconfirmed marker directly
        unconfirmed_id = f"unconfirmed_{datetime.now().timestamp()}"
        unconfirmed = ContinuityMarker(
            marker_id=unconfirmed_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=False,
            source_type="hindsight",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["unconfirmed"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[unconfirmed_id] = unconfirmed

        # Get recent markers - should only include confirmed
        recent = store.get_recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]

        assert confirmed["marker_id"] in marker_ids
        assert unconfirmed_id not in marker_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
