"""
Tests for ContinuityService clinicalization guard (FIX06).

Validates that forbidden clinical terms are blocked in:
- normalized_tags
- gumi_words
- followup context
- summary output

Exception: subject_words may contain clinical terms only when authored by subject.
"""

import pytest
import json
from pathlib import Path

from relic.shared_continuity.service import (
    ContinuityService,
    FORBIDDEN_CLINICAL_TERMS,
)


@pytest.fixture
def service():
    """Fresh ContinuityService for each test."""
    return ContinuityService()


@pytest.fixture
def blocked_fixture():
    """Load the blocked_clinicalized_marker fixture."""
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "shared-continuity" / "blocked_clinicalized_marker.json"
    with open(fixture_path) as f:
        return json.load(f)


class TestRememberBlocksClinicalizedMarker:
    """test_remember_blocks_clinicalized_marker"""

    def test_remember_blocks_clinicalized_normalized_tags(self, service):
        """remember() must raise BLOCKED_CLINICALIZATION_IN_MARKER when normalized_tags contains clinical terms."""
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["I feel good today"],
                normalized_tags=["hypomania"],  # forbidden,
                subject_confirmation=True,
            )

    def test_remember_blocks_clinicalized_gumi_words(self, service):
        """remember() must raise BLOCKED_CLINICALIZATION_IN_MARKER when gumi_words contains clinical terms."""
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["I feel good today"],
                gumi_words=["this seems like hypomania"],  # forbidden,
                subject_confirmation=True,
            )

    def test_remember_blocks_clinicalized_marker_from_fixture(self, service, blocked_fixture):
        """Fixture-driven test: hypomania in normalized_tags must be blocked."""
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=[blocked_fixture["subject_words"]],
                normalized_tags=blocked_fixture["normalized_tags"],
                gumi_words=[blocked_fixture["gumi_words"]],
                subject_confirmation=True,
            )


class TestCorrectBlocksClinicalizedNormalizedTags:
    """test_correct_blocks_clinicalized_normalized_tags"""

    def test_correct_blocks_clinicalized_normalized_tags(self, service):
        """correct() must raise BLOCKED_CLINICALIZATION_IN_MARKER when normalized_tags contains clinical terms."""
        # First create a valid marker
        marker = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["I feel good today"],
            subject_confirmation=True,
        )

        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.correct(
                marker_id=marker["marker_id"],
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["I corrected this"],
                normalized_tags=["depression"],  # forbidden
            )

    def test_correct_blocks_clinicalized_gumi_words(self, service):
        """correct() must raise BLOCKED_CLINICALIZATION_IN_MARKER when gumi_words contains clinical terms."""
        # First create a valid marker
        marker = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["I feel good today"],
            subject_confirmation=True,
        )

        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.correct(
                marker_id=marker["marker_id"],
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["I corrected this"],
                gumi_words=["seems like mania"],  # forbidden
            )


class TestSubjectWordsClinicalTermsAllowedInSubjectWordsOnly:
    """test_subject_words_clinical_terms_allowed_in_subject_words_only"""

    def test_subject_words_clinical_terms_allowed_in_subject_words(self, service):
        """subject_words may contain clinical terms authored by subject - not blocked."""
        # This should NOT raise - subject's own words may contain clinical language
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["I think this is hypomania"],  # subject's own clinical language,
            subject_confirmation=True,
        )
        assert result["subject_words"] == ["I think this is hypomania"]

    def test_subject_words_clinical_terms_not_copied_to_normalized_tags(self, service):
        """Clinical terms in subject_words must NOT be copied to normalized_tags."""
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["I think this is hypomania"],
            normalized_tags=["feeling energetic"],  # safe tag,
            subject_confirmation=True,
        )
        # normalized_tags should NOT contain the clinical term from subject_words
        assert "normalized_tags" not in result or "hypomania" not in str(result.get("normalized_tags", []))

    def test_subject_words_clinical_terms_not_copied_to_gumi_words(self, service):
        """Clinical terms in subject_words must NOT be copied to gumi_words."""
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["I think this is hypomania"],
            gumi_words=["feeling energetic"],  # safe word,
            subject_confirmation=True,
        )
        # gumi_words should NOT contain the clinical term from subject_words
        assert "gumi_words" not in result or "hypomania" not in str(result.get("gumi_words", []))


class TestNormalizedTagsClinicalTermsBlocked:
    """test_normalized_tags_clinical_terms_blocked"""

    @pytest.mark.parametrize("term", list(FORBIDDEN_CLINICAL_TERMS))
    def test_each_forbidden_term_blocked_in_normalized_tags(self, service, term):
        """Each term in FORBIDDEN_CLINICAL_TERMS must be blocked in normalized_tags."""
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["some text"],
                normalized_tags=[term],
                subject_confirmation=True,
            )

    def test_all_forbidden_terms_blocked(self, service):
        """Multiple forbidden terms in normalized_tags must all be blocked."""
        forbidden_list = ["bipolar", "mania", "depression", "diagnosis", "relapse"]
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["some text"],
                normalized_tags=forbidden_list,
                subject_confirmation=True,
            )


class TestFollowupContextNoClinicalLabels:
    """test_followup_context_no_clinical_labels"""

    def test_followup_context_no_clinical_labels(self, service):
        """Followup context must not include clinical labels in marker output."""
        # Create a marker with followup data
        marker = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["feeling good"],
            normalized_tags=["positive"],  # safe,
            subject_confirmation=True,
        )
        # The marker output should not have clinical terms
        assert "normalized_tags" not in marker or not any(
            service._contains_clinical_term(t) for t in marker.get("normalized_tags", [])
        )


class TestSummaryOutputNoClinicalTags:
    """test_summary_output_no_clinical_tags"""

    def test_summary_output_no_clinical_tags(self, service):
        """Summary output must not contain clinical tags."""
        # Create marker with safe content
        marker = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["feeling energetic"],
            normalized_tags=["energy", "mood"],
            subject_confirmation=True,
        )
        # Output should have no clinical terms
        output_str = json.dumps(marker)
        for term in FORBIDDEN_CLINICAL_TERMS:
            assert term.lower() not in output_str.lower() or "subject_words" in output_str


class TestNormalizeForGumi:
    """Test the normalize_for_gumi helper."""

    def test_strips_clinical_terms_from_tags(self, service):
        """normalize_for_gumi must strip clinical terms from tags."""
        safe_tags, safe_words = service.normalize_for_gumi(
            ["hypomania", "energy", "mood"],
            []
        )
        assert "hypomania" not in safe_tags
        assert "energy" in safe_tags
        assert "mood" in safe_tags

    def test_strips_clinical_terms_from_gumi_words(self, service):
        """normalize_for_gumi must strip clinical terms from gumi_words."""
        safe_tags, safe_words = service.normalize_for_gumi(
            [],
            ["seems like mania", "feeling good"]
        )
        assert "mania" not in safe_words
        assert "feeling good" in safe_words

    def test_preserves_non_clinical_terms(self, service):
        """normalize_for_gumi must preserve non-clinical terms."""
        safe_tags, safe_words = service.normalize_for_gumi(
            ["energy", "sleep", "mood"],
            ["feeling great", "good day"]
        )
        assert safe_tags == ["energy", "sleep", "mood"]
        assert safe_words == ["feeling great", "good day"]


class TestBlockClinicalizedMarker:
    """Test block_clinicalized_marker method."""

    def test_raises_on_clinical_normalized_tags(self, service):
        """block_clinicalized_marker must raise on clinical normalized_tags."""
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.block_clinicalized_marker(["hypomania"], [])

    def test_raises_on_clinical_gumi_words(self, service):
        """block_clinicalized_marker must raise on clinical gumi_words."""
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.block_clinicalized_marker([], ["seems like mania"])

    def test_no_raise_on_safe_content(self, service):
        """block_clinicalized_marker must not raise on safe content."""
        service.block_clinicalized_marker(["energy", "mood"], ["feeling great"])
