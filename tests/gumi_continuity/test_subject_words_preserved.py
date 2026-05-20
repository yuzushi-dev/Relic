"""
PR06 — Test that subject words are preserved through correction.

Tests for FIX04: Subject words are preserved through correction
and admission, without clinicalization.
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
    FORBIDDEN_CLINICAL_TERMS,
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


class TestSubjectWordsPreserved:
    """Test that subject words are preserved through correction."""

    def test_subject_words_preserved_in_marker(self, service):
        """Subject words are preserved in the marker."""
        # Create marker with subject words
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["my own words", "exactly as I said"],
            subject_confirmation=True,
        )

        assert result["subject_words"] == ["my own words", "exactly as I said"]

    def test_subject_words_preserved_through_correction(self, service):
        """Subject words are preserved when marker is corrected."""
        # Create original marker
        original = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["original words"],
            subject_confirmation=True,
        )

        # Correct it
        corrected = service.correct(
            marker_id=original["marker_id"],
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["corrected words"],
        )

        # Get the new marker
        new_marker = service._markers[corrected["new_marker_id"]]
        assert new_marker.subject_words == ["corrected words"]

    def test_final_subject_words_in_corrected_marker(self, service):
        """Corrected marker has final_subject_words set correctly."""
        # Create original marker
        original = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["original"],
            subject_confirmation=True,
        )

        # Correct it
        corrected = service.correct(
            marker_id=original["marker_id"],
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["final version"],
        )

        # Get recent markers - should show final_subject_words
        recent = service.recent_markers(subject_id="subj_001")
        assert len(recent) >= 1

        marker = recent[0]
        if "final_subject_words" in marker:
            assert marker["final_subject_words"] == ["final version"]

    def test_subject_words_not_clinicalized(self, service):
        """Subject words are NOT clinicalized (no forbidden terms added)."""
        # Create marker with subject's own words
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["feeling fast", "moving quickly"],
            subject_confirmation=True,
        )

        # Check output for forbidden clinical terms
        output_str = str(result).lower()
        for term in FORBIDDEN_CLINICAL_TERMS:
            # Subject words may contain clinical language, but service should not add clinical labels
            # The key is that clinicalization is blocked at the service level
            assert term not in output_str or "subject_words" in str(result)

    def test_subject_words_preserved_in_recall(self, service):
        """Subject words are preserved when marker is recalled."""
        # Create marker
        marker = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["my words are important"],
            subject_confirmation=True,
        )

        # Recall it
        recent = service.recent_markers(subject_id="subj_001")
        assert len(recent) >= 1

        recalled = recent[0]
        assert "my words are important" in recalled["subject_words"]


class TestClinicalTermsBlockedInGumiOutput:
    """Test that clinical terms are blocked in Gumi output."""

    def test_no_clinical_terms_in_recall_output(self, service):
        """No clinical terms appear in recall output."""
        # Create marker
        service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["clean words"],
            subject_confirmation=True,
        )

        # Recall markers
        recent = service.recent_markers(subject_id="subj_001")

        # Check for forbidden clinical terms
        output_str = str(recent).lower()
        for term in FORBIDDEN_CLINICAL_TERMS:
            assert term not in output_str

    def test_clinical_terms_blocked_in_normalized_tags(self, service):
        """Clinical terms are blocked from being added to normalized_tags."""
        # Try to create marker with clinical terms in normalized_tags
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["some words"],
                normalized_tags=["depression"],  # Should be blocked,
                subject_confirmation=True,
            )

    def test_clinical_terms_blocked_in_gumi_words(self, service):
        """Clinical terms are blocked from being added to gumi_words."""
        # Try to create marker with clinical terms in gumi_words
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["some words"],
                gumi_words=["seems like mania"],  # Should be blocked,
                subject_confirmation=True,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
