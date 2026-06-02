"""
PR06, Test TTL and Recall Limit enforcement.

Tests for FIX03: TTL (Time To Live) and recall limit enforcement
in Gumi continuity recall.
"""

import pytest
from datetime import datetime, timedelta

from relic.gumi_continuity import (
    GumiContinuityStore,
    ContinuityAdmissionPolicy,
    check_recall_eligibility,
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


class TestTTLEnforcement:
    """Test TTL (Time To Live) enforcement."""

    def test_expired_marker_not_recalled(self, service, admission_policy):
        """Expired marker (expires_at in past) is NOT recalled."""
        marker_id = f"expired_{datetime.now().timestamp()}"
        # Expired 7 days ago
        expired_time = (datetime.now() - timedelta(days=7)).isoformat() + "Z"

        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["expired marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=expired_time,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        # Verify it's NOT recalled
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id not in marker_ids

    def test_active_marker_with_no_ttl_recalled(self, service, admission_policy):
        """Marker with no TTL (expires_at=null) IS recalled."""
        marker_id = f"no_ttl_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["no TTL marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=0,
            expires_at=None,  # No TTL
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        # Verify it's recalled
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id in marker_ids

    def test_not_yet_expired_marker_recalled(self, service, admission_policy):
        """Marker not yet expired IS recalled."""
        marker_id = f"not_expired_{datetime.now().timestamp()}"
        # Expires in 7 days
        future_time = (datetime.now() + timedelta(days=7)).isoformat() + "Z"

        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["not expired marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=future_time,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        # Verify it's recalled
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id in marker_ids

    def test_admission_policy_blocks_expired_marker(self, admission_policy):
        """Admission policy correctly blocks expired markers."""
        expired_marker = {
            "marker_id": "expired_001",
            "subject_id": "subj_001",
            "gumi_instance_id": "gumi_001",
            "hermes_profile_id": "hermes_001",
            "subject_confirmation": True,
            "status": "active",
            "gumi_recall_allowed": True,
            "recall_count": 0,
            "max_recall_count": 3,
            "expires_at": (datetime.now() - timedelta(days=1)).isoformat() + "Z",
        }

        decision = admission_policy.evaluate_marker(expired_marker)
        assert decision.admitted is False
        assert decision.blocked_by == "ttl"


class TestRecallLimitEnforcement:
    """Test recall limit enforcement."""

    def test_marker_at_max_recall_not_recalled(self, service, admission_policy):
        """Marker at max_recall_count is NOT recalled."""
        marker_id = f"max_recall_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["max recall marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=3,  # At max_recall_count
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

    def test_marker_below_max_recall_recalled(self, service, admission_policy):
        """Marker below max_recall_count IS recalled."""
        marker_id = f"below_max_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["below max recall marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=2,  # Below max_recall_count
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        # Verify it's recalled
        recent = service.recent_markers(subject_id="subj_001")
        marker_ids = [m["marker_id"] for m in recent]
        assert marker_id in marker_ids

    def test_admission_policy_blocks_max_recall_marker(self, admission_policy):
        """Admission policy correctly blocks markers at max recall."""
        max_recall_marker = {
            "marker_id": "max_001",
            "subject_id": "subj_001",
            "gumi_instance_id": "gumi_001",
            "hermes_profile_id": "hermes_001",
            "subject_confirmation": True,
            "status": "active",
            "gumi_recall_allowed": True,
            "recall_count": 3,
            "max_recall_count": 3,
            "expires_at": None,
        }

        decision = admission_policy.evaluate_marker(max_recall_marker)
        assert decision.admitted is False
        assert decision.blocked_by == "recall_limit"


class TestCheckRecallEligibility:
    """Test check_recall_eligibility() function."""

    def test_eligible_marker(self, service):
        """check_recall_eligibility() returns eligible for valid marker."""
        marker_id = f"eligible_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["eligible marker"],
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

        result = check_recall_eligibility(marker_id, store=service)
        assert result["eligible"] is True

    def test_ineligible_due_to_expired(self, service):
        """check_recall_eligibility() returns ineligible for expired marker."""
        marker_id = f"check_expired_{datetime.now().timestamp()}"
        expired_time = (datetime.now() - timedelta(days=1)).isoformat() + "Z"

        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["check expired marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=expired_time,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        result = check_recall_eligibility(marker_id, store=service)
        assert result["eligible"] is False
        assert "expired" in result["reason"].lower()

    def test_ineligible_due_to_max_recall(self, service):
        """check_recall_eligibility() returns ineligible for max recall."""
        marker_id = f"check_max_{datetime.now().timestamp()}"
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at=datetime.now().isoformat() + "Z",
            subject_words=["check max marker"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=3,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at=datetime.now().isoformat() + "Z",
        )
        service._markers[marker_id] = marker

        result = check_recall_eligibility(marker_id, store=service)
        assert result["eligible"] is False
        assert "recall limit" in result["reason"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
