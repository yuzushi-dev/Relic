"""
FIX08: Authoritative correction recall tests.

Verifies:
- Corrected markers are NOT selected for Gumi context
- recent_markers resolves to latest authoritative marker
- Summary uses final_subject_words from latest authoritative marker
- Replacement chain is traversable
- Old marker status is corrected
"""

import pytest
from datetime import datetime, timedelta
from relic.shared_continuity.service import (
    ContinuityService,
    MarkerStatus,
    get_continuity_service,
)


@pytest.fixture
def service():
    """Fresh service for each test."""
    return ContinuityService()


@pytest.fixture
def subject_scope():
    """Standard subject scope."""
    return {
        "subject_id": "subject_1",
        "gumi_instance_id": "gumi_1",
        "hermes_profile_id": "hermes_1",
    }


@pytest.fixture
def base_marker(service, subject_scope):
    """Create a base marker for correction tests."""
    marker = service.remember(
        subject_id=subject_scope["subject_id"],
        gumi_instance_id=subject_scope["gumi_instance_id"],
        hermes_profile_id=subject_scope["hermes_profile_id"],
        subject_words=["accelerated", "racing thoughts"],
        source_type="user_confirmed",
        max_recall_count=3,
        ttl_seconds=604800,
    )
    return marker


class TestCorrectedMarkerNotSelectedForGumiContext:
    """Test that corrected/replaced markers are not selected for Gumi context."""

    def test_corrected_marker_not_selected_for_gumi_context(self, service, subject_scope, base_marker):
        """
        Old marker after correct() must NOT be selected for Gumi context.
        gumi_recall_allowed should be False.
        """
        old_marker_id = base_marker["marker_id"]

        # Correct the marker
        result = service.correct(
            marker_id=old_marker_id,
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["happy, high energy, low sleep"],
        )

        # Get the old marker directly from storage
        old_marker = service._markers[old_marker_id]

        # Old marker must NOT be recall-eligible for Gumi
        assert old_marker.gumi_recall_allowed is False, \
            "Old marker should have gumi_recall_allowed=False after correction"

        # Old marker status should be CORRECTED
        assert old_marker.status == MarkerStatus.CORRECTED, \
            f"Old marker status should be CORRECTED, got {old_marker.status}"

        # recent_markers should NOT return the corrected marker
        recent = service.recent_markers(subject_id=subject_scope["subject_id"])
        marker_ids = [m["marker_id"] for m in recent]
        assert old_marker_id not in marker_ids, \
            "Corrected marker should not appear in recent_markers"

    def test_new_marker_is_recall_eligible(self, service, subject_scope, base_marker):
        """New marker created by correct() should be recall-eligible."""
        old_marker_id = base_marker["marker_id"]

        result = service.correct(
            marker_id=old_marker_id,
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["happy, high energy, low sleep"],
        )

        new_marker_id = result["new_marker_id"]
        new_marker = service._markers[new_marker_id]

        assert new_marker.gumi_recall_allowed is True
        assert new_marker.status == MarkerStatus.ACTIVE


class TestRecentMarkersResolvesLatestAuthoritative:
    """Test that recent_markers resolves to latest authoritative marker."""

    def test_recent_markers_resolves_latest_authoritative(self, service, subject_scope, base_marker):
        """
        When a marker has a replacement chain, recent_markers should return
        the latest authoritative marker, not intermediate ones.
        """
        old_marker_id = base_marker["marker_id"]

        # First correction
        result1 = service.correct(
            marker_id=old_marker_id,
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["first correction"],
        )
        first_corrected_id = result1["new_marker_id"]

        # Second correction
        result2 = service.correct(
            marker_id=first_corrected_id,
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["final authoritative version"],
        )
        final_marker_id = result2["new_marker_id"]

        # Get recent markers
        recent = service.recent_markers(subject_id=subject_scope["subject_id"])

        # Should contain only the final authoritative marker
        marker_ids = [m["marker_id"] for m in recent]
        assert final_marker_id in marker_ids, \
            "Final authoritative marker should be in recent_markers"
        assert first_corrected_id not in marker_ids, \
            "Intermediate corrected marker should not appear"
        assert old_marker_id not in marker_ids, \
            "Original marker should not appear"

        # The returned marker should have final_subject_words
        final_marker = recent[0]
        assert final_marker["marker_id"] == final_marker_id
        assert final_marker.get("final_subject_words") == ["final authoritative version"]


class TestSummaryUsesFinalSubjectWords:
    """Test that summary output uses final_subject_words from latest authoritative marker."""

    def test_summary_uses_final_subject_words(self, service, subject_scope, base_marker):
        """
        Summary output must use final_subject_words from the latest authoritative marker.
        """
        old_marker_id = base_marker["marker_id"]

        # Correct the marker
        result = service.correct(
            marker_id=old_marker_id,
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["happy, high energy, low sleep"],
        )

        new_marker_id = result["new_marker_id"]

        # Get recent markers (which is used for summary)
        recent = service.recent_markers(subject_id=subject_scope["subject_id"])

        assert len(recent) == 1
        marker = recent[0]

        # The marker should carry final_subject_words
        assert marker.get("final_subject_words") == ["happy, high energy, low sleep"], \
            "Summary should use final_subject_words from latest authoritative marker"

        # subject_words should also reflect the latest
        assert marker["subject_words"] == ["happy, high energy, low sleep"]


class TestReplacementChainTraversable:
    """Test that replacement chain is traversable."""

    def test_replacement_chain_traversable(self, service, subject_scope, base_marker):
        """
        When selecting a marker, if it has previous_version_id, follow the chain
        to find the latest authoritative version.
        """
        old_marker_id = base_marker["marker_id"]

        # First correction
        result1 = service.correct(
            marker_id=old_marker_id,
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["first correction"],
        )
        first_corrected_id = result1["new_marker_id"]

        # Second correction
        result2 = service.correct(
            marker_id=first_corrected_id,
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["final version"],
        )
        final_marker_id = result2["new_marker_id"]

        # Verify the chain
        final_marker = service._markers[final_marker_id]
        assert final_marker.previous_version_id == first_corrected_id

        first_marker = service._markers[first_corrected_id]
        assert first_marker.previous_version_id == old_marker_id

        original_marker = service._markers[old_marker_id]
        assert original_marker.status == MarkerStatus.CORRECTED

        # Test _get_latest_authoritative_marker traversal
        latest = service._get_latest_authoritative_marker(final_marker)
        assert latest.marker_id == final_marker_id

        latest_from_first = service._get_latest_authoritative_marker(first_marker)
        assert latest_from_first.marker_id == final_marker_id

        latest_from_original = service._get_latest_authoritative_marker(original_marker)
        assert latest_from_original.marker_id == final_marker_id

    def test_single_marker_no_chain(self, service, subject_scope, base_marker):
        """Marker without previous_version_id returns itself."""
        marker_id = base_marker["marker_id"]
        marker = service._markers[marker_id]

        latest = service._get_latest_authoritative_marker(marker)
        assert latest.marker_id == marker_id


class TestOldMarkerStatusIsCorrected:
    """Test that old marker status is correctly set to CORRECTED."""

    def test_old_marker_status_is_corrected(self, service, subject_scope, base_marker):
        """
        After correct(), old marker status should be CORRECTED, not RETIRED.
        """
        old_marker_id = base_marker["marker_id"]

        result = service.correct(
            marker_id=old_marker_id,
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["new words"],
        )

        old_marker = service._markers[old_marker_id]

        assert old_marker.status == MarkerStatus.CORRECTED, \
            f"Expected status CORRECTED, got {old_marker.status}"

    def test_fixture_scenario(self, service, subject_scope):
        """
        Test the fixture scenario: corrected marker has status CORRECTED
        and gumi_recall_allowed=False.
        """
        # Create old marker
        old_marker = service.remember(
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["accelerated"],
            source_type="user_confirmed",
            max_recall_count=3,
            ttl_seconds=604800,
        )

        # Correct it
        result = service.correct(
            marker_id=old_marker["marker_id"],
            subject_id=subject_scope["subject_id"],
            gumi_instance_id=subject_scope["gumi_instance_id"],
            hermes_profile_id=subject_scope["hermes_profile_id"],
            subject_words=["happy, high energy, low sleep"],
        )

        # Verify expected_recall_marker_id is the new marker
        assert result["new_marker_id"] is not None
        assert result["authoritative"] is True

        # Old marker should be corrected
        old = service._markers[old_marker["marker_id"]]
        assert old.status == MarkerStatus.CORRECTED
        assert old.gumi_recall_allowed is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
