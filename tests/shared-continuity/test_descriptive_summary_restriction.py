"""
FIX10, Descriptive Summary Restriction Tests

Tests for get_descriptive_summary_markers() which restricts summaries to:
- source_type in: subject_confirmed, subject_requested, subject_corrected
- clinical_interpretation_allowed = False
- status != rejected
- status != forgotten
- gumi_recall_allowed = True

Excludes:
- safety signals
- unconfirmed candidates
- researcher-only notes
- clinical tags
- hidden evidence
"""

import pytest
from relic.shared_continuity.service import (
    ContinuityService,
    ContinuityMarker,
    MarkerStatus,
)


def _create_marker(
    service: ContinuityService,
    subject_id: str,
    source_type: str,
    status: MarkerStatus = MarkerStatus.ACTIVE,
    gumi_recall_allowed: bool = True,
    clinical_interpretation_allowed: bool = False,
    candidate_for_confirmation: bool = False,
) -> ContinuityMarker:
    """Helper to create a marker directly in the service's internal store."""
    marker_id = f"marker_{subject_id}_{len(service._markers)}"
    marker = ContinuityMarker(
        marker_id=marker_id,
        subject_id=subject_id,
        gumi_instance_id="gumi_001",
        hermes_profile_id="hermes_001",
        subject_confirmation=True,
        source_type=source_type,
        created_at="2024-01-01T00:00:00Z",
        subject_words=["test words"],
        gumi_agreed_words=[],
        raw_source_text=None,
        status=status,
        gumi_recall_allowed=gumi_recall_allowed,
        recall_count=0,
        max_recall_count=3,
        ttl_seconds=604800,
        expires_at=None,
        updated_at="2024-01-01T00:00:00Z",
        candidate_for_confirmation=candidate_for_confirmation,
        clinical_interpretation_allowed=clinical_interpretation_allowed,
    )
    service._markers[marker_id] = marker
    return marker


class TestDescriptiveSummaryRestriction:
    """Tests for descriptive summary marker restriction."""

    def test_summary_uses_only_subject_confirmed_markers(self):
        """get_descriptive_summary_markers returns only subject_confirmed/requested/corrected."""
        service = ContinuityService()

        # Create markers with different source types
        _create_marker(service, "subj_001", "subject_confirmed")
        _create_marker(service, "subj_001", "subject_requested")
        _create_marker(service, "subj_001", "subject_corrected")
        _create_marker(service, "subj_001", "hindsight_safety_signal")  # Should be excluded
        _create_marker(service, "subj_001", "researcher_only_note")  # Should be excluded
        _create_marker(service, "subj_001", "system_inferred")  # Should be excluded

        results = service.get_descriptive_summary_markers(subject_id="subj_001")

        # Only the three subject-confirmed types should be returned
        assert len(results) == 3
        source_types = {r["source_type"] for r in results}
        assert source_types == {"subject_confirmed", "subject_requested", "subject_corrected"}

    def test_summary_excludes_rejected_markers(self):
        """get_descriptive_summary_markers excludes markers with status=rejected."""
        service = ContinuityService()

        # Create a normal marker
        _create_marker(service, "subj_001", "subject_confirmed", status=MarkerStatus.ACTIVE)

        # Create a rejected marker
        _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            status=MarkerStatus.REJECTED,
        )

        results = service.get_descriptive_summary_markers(subject_id="subj_001")

        assert len(results) == 1
        assert results[0]["status"] == "active"

    def test_summary_excludes_forgotten_markers(self):
        """get_descriptive_summary_markers excludes markers with status=forgotten."""
        service = ContinuityService()

        # Create a normal marker
        _create_marker(service, "subj_001", "subject_confirmed", status=MarkerStatus.ACTIVE)

        # Create a forgotten marker
        _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            status=MarkerStatus.FORGOTTEN,
        )

        results = service.get_descriptive_summary_markers(subject_id="subj_001")

        assert len(results) == 1
        assert results[0]["status"] == "active"

    def test_summary_excludes_unconfirmed_candidates(self):
        """get_descriptive_summary_markers excludes unconfirmed candidates."""
        service = ContinuityService()

        # Create a normal marker
        _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            candidate_for_confirmation=False,
        )

        # Create an unconfirmed candidate
        candidate_marker = _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            candidate_for_confirmation=True,
        )

        results = service.get_descriptive_summary_markers(subject_id="subj_001")

        assert len(results) == 1
        # Verify the returned marker is NOT the candidate
        assert results[0]["marker_id"] != candidate_marker.marker_id

    def test_summary_excludes_clinical_interpretation_allowed_markers(self):
        """get_descriptive_summary_markers excludes markers with clinical_interpretation_allowed=True."""
        service = ContinuityService()

        # Create a normal marker with clinical_interpretation_allowed=False
        _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            clinical_interpretation_allowed=False,
        )

        # Create a marker with clinical_interpretation_allowed=True (clinical tag)
        _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            clinical_interpretation_allowed=True,
        )

        results = service.get_descriptive_summary_markers(subject_id="subj_001")

        assert len(results) == 1
        # Verify the returned marker has clinical_interpretation_allowed=False
        marker_id = results[0]["marker_id"]
        assert service._markers[marker_id].clinical_interpretation_allowed is False

    def test_summary_excludes_hidden_evidence(self):
        """get_descriptive_summary_markers excludes markers with gumi_recall_allowed=False."""
        service = ContinuityService()

        # Create a normal marker
        _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            gumi_recall_allowed=True,
        )

        # Create a hidden evidence marker
        _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            gumi_recall_allowed=False,
        )

        results = service.get_descriptive_summary_markers(subject_id="subj_001")

        assert len(results) == 1
        assert results[0]["gumi_recall_allowed"] is True

    def test_summary_respects_subject_scope(self):
        """get_descriptive_summary_markers only returns markers for the specified subject."""
        service = ContinuityService()

        _create_marker(service, "subj_001", "subject_confirmed")
        _create_marker(service, "subj_002", "subject_confirmed")

        results = service.get_descriptive_summary_markers(subject_id="subj_001")

        assert len(results) == 1
        assert results[0]["subject_id"] == "subj_001"

    def test_summary_applies_all_filters_combined(self):
        """get_descriptive_summary_markers correctly applies all filters together."""
        service = ContinuityService()

        # This marker should appear: valid source_type, active, recall_allowed, no clinical interpretation
        _create_marker(
            service,
            "subj_001",
            "subject_confirmed",
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            clinical_interpretation_allowed=False,
            candidate_for_confirmation=False,
        )

        # These should be excluded:
        _create_marker(service, "subj_001", "hindsight_safety_signal")  # invalid source_type
        _create_marker(service, "subj_001", "subject_confirmed", status=MarkerStatus.REJECTED)  # rejected
        _create_marker(service, "subj_001", "subject_confirmed", gumi_recall_allowed=False)  # hidden
        _create_marker(service, "subj_001", "subject_confirmed", clinical_interpretation_allowed=True)  # clinical
        _create_marker(service, "subj_001", "subject_confirmed", candidate_for_confirmation=True)  # candidate

        results = service.get_descriptive_summary_markers(subject_id="subj_001")

        assert len(results) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])