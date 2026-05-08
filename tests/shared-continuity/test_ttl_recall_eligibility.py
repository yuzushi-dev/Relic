"""
FIX07: TTL and Recall Eligibility Tests

Tests for marker recall eligibility based on:
- status == ACTIVE
- expires_at is null OR expires_at > now
- recall_count < max_recall_count
- gumi_recall_allowed == true
- scope not paused
"""

import pytest
from datetime import datetime, timedelta

from relic.shared_continuity.service import (
    ContinuityService,
    MarkerStatus,
    get_continuity_service,
)


class TestTTLRecallEligibility:
    """Tests for TTL and recall eligibility in ContinuityService."""

    def setup_method(self):
        """Reset service before each test."""
        # Create a fresh service instance for testing
        self.service = ContinuityService()

    def _create_marker_with_defaults(self, **overrides):
        """Helper to create a marker with test values."""
        marker_id = f"marker_{datetime.now().timestamp()}"
        subject_id = overrides.get("subject_id", "subject_001")
        gumi_instance_id = overrides.get("gumi_instance_id", "gumi_001")
        hermes_profile_id = overrides.get("hermes_profile_id", "hermes_001")
        now = datetime.now()
        created_at = now.isoformat() + "Z"
        expires_at = (now + timedelta(seconds=604800)).isoformat() + "Z"

        marker = {
            "marker_id": marker_id,
            "subject_id": subject_id,
            "gumi_instance_id": gumi_instance_id,
            "hermes_profile_id": hermes_profile_id,
            "subject_confirmation": True,
            "source_type": "user_confirmed",
            "created_at": created_at,
            "subject_words": ["test", "words"],
            "gumi_agreed_words": [],
            "raw_source_text": None,
            "status": MarkerStatus.ACTIVE,
            "gumi_recall_allowed": True,
            "recall_count": 0,
            "max_recall_count": 3,
            "ttl_seconds": 604800,
            "expires_at": expires_at,
            "updated_at": created_at,
        }
        marker.update(overrides)
        return marker

    def _insert_marker(self, **overrides):
        """Insert a marker directly into the service's internal store."""
        marker_data = self._create_marker_with_defaults(**overrides)
        from relic.shared_continuity.service import ContinuityMarker
        marker_obj = ContinuityMarker(**marker_data)
        self.service._markers[marker_data["marker_id"]] = marker_obj
        return marker_obj

    def test_expired_marker_not_recalled(self):
        """An expired marker (expires_at in past) is NOT recall-eligible."""
        now = datetime.now()
        # Create an expired marker - expired 7 days ago
        expired_time = (now - timedelta(days=7)).isoformat() + "Z"

        marker = self._insert_marker(
            marker_id="cm_expired_001",
            status=MarkerStatus.ACTIVE,
            expires_at=expired_time,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            subject_confirmation=True,
        )

        # Verify the marker is NOT returned by recent_markers
        results = self.service.recent_markers(
            subject_id=marker.subject_id,
            gumi_instance_id=marker.gumi_instance_id,
            hermes_profile_id=marker.hermes_profile_id,
        )

        assert len(results) == 0, "Expired marker should NOT be recalled"
        assert all(m["marker_id"] != "cm_expired_001" for m in results)

    def test_active_marker_with_no_ttl_recalled(self):
        """A marker with no TTL (expires_at=null) IS recall-eligible."""
        marker = self._insert_marker(
            marker_id="cm_no_ttl_001",
            status=MarkerStatus.ACTIVE,
            expires_at=None,  # No TTL
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            subject_confirmation=True,
        )

        results = self.service.recent_markers(
            subject_id=marker.subject_id,
            gumi_instance_id=marker.gumi_instance_id,
            hermes_profile_id=marker.hermes_profile_id,
        )

        assert len(results) == 1
        assert results[0]["marker_id"] == "cm_no_ttl_001"

    def test_marker_at_max_recall_not_recalled(self):
        """A marker at max_recall_count is NOT recall-eligible."""
        marker = self._insert_marker(
            marker_id="cm_max_recall_001",
            status=MarkerStatus.ACTIVE,
            expires_at=None,  # No TTL
            gumi_recall_allowed=True,
            recall_count=3,  # At max_recall_count
            max_recall_count=3,
            subject_confirmation=True,
        )

        results = self.service.recent_markers(
            subject_id=marker.subject_id,
            gumi_instance_id=marker.gumi_instance_id,
            hermes_profile_id=marker.hermes_profile_id,
        )

        assert len(results) == 0, "Marker at max recall should NOT be recalled"
        assert all(m["marker_id"] != "cm_max_recall_001" for m in results)

    def test_marker_with_paused_scope_not_recalled(self):
        """A marker in a paused scope is NOT recall-eligible."""
        marker = self._insert_marker(
            marker_id="cm_paused_scope_001",
            status=MarkerStatus.ACTIVE,
            expires_at=None,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            subject_confirmation=True,
            subject_id="subject_paused",
            gumi_instance_id="gumi_paused",
            hermes_profile_id="hermes_paused",
        )

        # Pause the scope
        self.service.pause(
            subject_id="subject_paused",
            gumi_instance_id="gumi_paused",
            hermes_profile_id="hermes_paused",
            scope_name="global",
        )

        results = self.service.recent_markers(
            subject_id="subject_paused",
            gumi_instance_id="gumi_paused",
            hermes_profile_id="hermes_paused",
        )

        assert len(results) == 0, "Marker in paused scope should NOT be recalled"
        assert all(m["marker_id"] != "cm_paused_scope_001" for m in results)

    def test_gumi_recall_allowed_false_not_recalled(self):
        """A marker with gumi_recall_allowed=False is NOT recall-eligible."""
        marker = self._insert_marker(
            marker_id="cm_recall_false_001",
            status=MarkerStatus.ACTIVE,
            expires_at=None,
            gumi_recall_allowed=False,  # Explicitly not allowed
            recall_count=0,
            max_recall_count=3,
            subject_confirmation=True,
        )

        results = self.service.recent_markers(
            subject_id=marker.subject_id,
            gumi_instance_id=marker.gumi_instance_id,
            hermes_profile_id=marker.hermes_profile_id,
        )

        assert len(results) == 0, "Marker with gumi_recall_allowed=False should NOT be recalled"
        assert all(m["marker_id"] != "cm_recall_false_001" for m in results)
