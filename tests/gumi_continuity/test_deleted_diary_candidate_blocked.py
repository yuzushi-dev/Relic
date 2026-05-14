"""
PR06 — Test that deleted diary candidates are blocked.

Tests for FIX02: Deleted diary entries/world-state snapshots
are blocked from entering Gumi runtime context.
"""

import pytest
from datetime import datetime, timedelta

from relic.gumi_continuity import (
    GumiContinuityStore,
    ContinuityAdmissionPolicy,
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


class TestDeletedDiaryCandidateBlocked:
    """Test that deleted diary candidates are blocked."""

    def test_rejected_marker_not_recalled(self, service, admission_policy):
        """Rejected marker (status=rejected) is NOT recalled."""
        marker_id = f"rejected_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="diary_entry",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["rejected diary entry"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.REJECTED,  # Marked as rejected
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        # Verify it's NOT recalled
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id not in marker_ids

    def test_forgotten_marker_not_recalled(self, service, admission_policy):
        """Forgotten marker (status=forgotten) is NOT recalled."""
        marker_id = f"forgotten_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="diary_entry",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["forgotten diary entry"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.FORGOTTEN,  # Marked as forgotten
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        # Verify it's NOT recalled
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id not in marker_ids

    def test_forget_method_blocks_recall(self, service, admission_policy):
        """forget() method correctly blocks recall."""
        # Create an active marker
        marker_id = f"to_forget_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="diary_entry",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["active diary entry"],
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

        # Verify it's recalled initially
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id in marker_ids

        # Forget it
        service.forget(marker_id=marker_id, subject_id="subj_001")

        # Verify it's NOT recalled after forget
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id not in marker_ids

    def test_corrected_marker_not_recalled(self, service, admission_policy):
        """Corrected marker (old version) is NOT recalled."""
        # Create an original marker
        original_id = f"original_{datetime.now().timestamp()}"
        original = ContinuityMarker(
            marker_id=original_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="diary_entry",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["original entry"],
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
        service._markers[original_id] = original

        # Correct it
        result = service.correct(
            marker_id=original_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["corrected entry"],
        )

        # The original (now corrected) should NOT be recalled
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert original_id not in marker_ids

        # But the new corrected marker should be recalled
        new_marker_id = result["new_marker_id"]
        assert new_marker_id in marker_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
