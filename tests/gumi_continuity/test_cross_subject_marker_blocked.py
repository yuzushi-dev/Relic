"""
PR06, Test that cross-subject markers are blocked.

Tests for FIX05: Markers from other subjects are blocked from
entering Gumi runtime context.
"""

import pytest
from datetime import datetime, timedelta

from relic.gumi_continuity import (
    GumiContinuityStore,
    ContinuityAdmissionPolicy,
    recall_eligible_markers,
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


class TestCrossSubjectMarkerBlocked:
    """Test that cross-subject markers are blocked."""

    def test_subject_001_markers_not_in_subject_002_recall(self, service):
        """Markers from subj_001 are NOT recalled by subj_002."""
        # Create marker for subj_001
        marker_1_id = f"subj1_{datetime.now().timestamp()}"
        marker_1 = ContinuityMarker(
            marker_id=marker_1_id,
            subject_id="subj_001",  # Subject 1
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["subj_001 marker"],
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
        service._markers[marker_1_id] = marker_1

        # Create marker for subj_002
        marker_2_id = f"subj2_{datetime.now().timestamp()}"
        marker_2 = ContinuityMarker(
            marker_id=marker_2_id,
            subject_id="subj_002",  # Subject 2
            gumi_instance_id="gumi_002",
            hermes_profile_id="hermes_002",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["subj_002 marker"],
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
        service._markers[marker_2_id] = marker_2

        # Get markers for subj_001 - should NOT include subj_002's marker
        markers_subj1 = service.recent_markers(subject_id="subj_001")
        marker_ids_subj1 = [m["marker_id"] for m in markers_subj1]
        assert marker_2_id not in marker_ids_subj1

        # Get markers for subj_002 - should NOT include subj_001's marker
        markers_subj2 = service.recent_markers(subject_id="subj_002")
        marker_ids_subj2 = [m["marker_id"] for m in markers_subj2]
        assert marker_1_id not in marker_ids_subj2

    def test_gumi_instance_isolation(self, service):
        """Markers from different gumi instances are isolated."""
        # Create markers with different gumi instances
        marker_a_id = f"gumi_a_{datetime.now().timestamp()}"
        marker_a = ContinuityMarker(
            marker_id=marker_a_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_a",  # Instance A
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["gumi_a marker"],
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
        service._markers[marker_a_id] = marker_a

        marker_b_id = f"gumi_b_{datetime.now().timestamp()}"
        marker_b = ContinuityMarker(
            marker_id=marker_b_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_b",  # Instance B
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["gumi_b marker"],
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
        service._markers[marker_b_id] = marker_b

        # Get markers for gumi_a - should only include gumi_a's marker
        markers_gumi_a = service.recent_markers(
            subject_id="subj_001",
            gumi_instance_id="gumi_a",
        )
        marker_ids_a = [m["marker_id"] for m in markers_gumi_a]
        assert marker_a_id in marker_ids_a
        assert marker_b_id not in marker_ids_a

        # Get markers for gumi_b - should only include gumi_b's marker
        markers_gumi_b = service.recent_markers(
            subject_id="subj_001",
            gumi_instance_id="gumi_b",
        )
        marker_ids_b = [m["marker_id"] for m in markers_gumi_b]
        assert marker_b_id in marker_ids_b
        assert marker_a_id not in marker_ids_b

    def test_hermes_profile_isolation(self, service):
        """Markers from different hermes profiles are isolated."""
        # Create markers with different hermes profiles
        marker_h1_id = f"hermes1_{datetime.now().timestamp()}"
        marker_h1 = ContinuityMarker(
            marker_id=marker_h1_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_1",  # Profile 1
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["hermes_1 marker"],
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
        service._markers[marker_h1_id] = marker_h1

        marker_h2_id = f"hermes2_{datetime.now().timestamp()}"
        marker_h2 = ContinuityMarker(
            marker_id=marker_h2_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_2",  # Profile 2
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["hermes_2 marker"],
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
        service._markers[marker_h2_id] = marker_h2

        # Get markers for hermes_1 - should only include hermes_1's marker
        markers_h1 = service.recent_markers(
            subject_id="subj_001",
            hermes_profile_id="hermes_1",
        )
        marker_ids_h1 = [m["marker_id"] for m in markers_h1]
        assert marker_h1_id in marker_ids_h1

        # Get markers for hermes_2 - should only include hermes_2's marker
        markers_h2 = service.recent_markers(
            subject_id="subj_001",
            hermes_profile_id="hermes_2",
        )
        marker_ids_h2 = [m["marker_id"] for m in markers_h2]
        assert marker_h2_id in marker_ids_h2

    def test_pause_scope_is_subject_scoped(self, service):
        """Pausing is scoped to subject."""
        # Create marker for subj_001
        marker_1_id = f"pause_subj1_{datetime.now().timestamp()}"
        marker_1 = ContinuityMarker(
            marker_id=marker_1_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["pause subj_001 marker"],
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
        service._markers[marker_1_id] = marker_1

        # Create marker for subj_002
        marker_2_id = f"pause_subj2_{datetime.now().timestamp()}"
        marker_2 = ContinuityMarker(
            marker_id=marker_2_id,
            subject_id="subj_002",
            gumi_instance_id="gumi_002",
            hermes_profile_id="hermes_002",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["pause subj_002 marker"],
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
        service._markers[marker_2_id] = marker_2

        # Pause subj_001's scope
        service.pause(
            subject_id="subj_001",
            scope_name="global",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        # subj_001's markers should NOT be recalled
        recent_1 = service.recent_markers(subject_id="subj_001")
        marker_ids_1 = [m["marker_id"] for m in recent_1]
        assert marker_1_id not in marker_ids_1

        # subj_002's markers SHOULD still be recalled
        recent_2 = service.recent_markers(subject_id="subj_002")
        marker_ids_2 = [m["marker_id"] for m in recent_2]
        assert marker_2_id in marker_ids_2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
