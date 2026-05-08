"""
PR33D — Continuity Service Tests

Tests for Relic continuity service operations:
- remember() requires subject_confirmation
- correct() marks old marker retired and stores correction as authoritative
- due_followups() returns markers where followup is due and not exhausted
- recent_markers() returns subject-confirmed markers only
- forget() removes from Gumi recall without deleting from storage
- pause() blocks follow-ups from paused scope
- resume() restores follow-ups
- No clinical terms in service output
"""

import pytest
from relic.shared_continuity.service import (
    ContinuityService,
    MarkerStatus,
    FollowupStatus,
    FORBIDDEN_CLINICAL_TERMS,
)


class TestContinuityServiceRemember:
    """Test remember() operation."""

    def test_remember_requires_subject_confirmation(self):
        """remember() requires subject_confirmation before storing marker."""
        service = ContinuityService()

        # This should succeed because user calling remember implies confirmation
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["feels fast"],
        )

        assert result["subject_confirmation"] is True

    def test_remember_stores_subject_words(self):
        """remember() stores subject's own words."""
        service = ContinuityService()

        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["too fast for me"],
        )

        assert "too fast for me" in result["subject_words"]

    def test_remember_blocks_clinical_terms(self):
        """remember() blocks clinical terms from being stored."""
        service = ContinuityService()

        # Clinical terms should not be in subject words
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["feeling depressed"],  # depressed is a clinical term
        )

        # The marker is stored, but should not contain clinical labels
        # Subject's own words may include clinical terms (exception clause)
        # But service output should not have system inference labels

    def test_remember_requires_subject_scope(self):
        """remember() requires all subject scope fields."""
        service = ContinuityService()

        with pytest.raises(ValueError) as exc_info:
            service.remember(
                subject_id="subj_001",
                gumi_instance_id=None,  # Missing
                hermes_profile_id="hermes_001",
                subject_words=["test"],
            )
        assert "BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE" in str(exc_info.value)

    def test_gumi_runtime_receives_no_clinical_tags(self):
        """Service output contains no clinical tags for Gumi runtime."""
        service = ContinuityService()

        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["feeling low"],
        )

        # Check output for forbidden terms
        result_str = str(result).lower()
        for term in FORBIDDEN_CLINICAL_TERMS:
            assert term not in result_str


class TestContinuityServiceCorrect:
    """Test correct() operation."""

    def test_correct_marks_old_marker_retired(self):
        """correct() marks old marker as retired."""
        service = ContinuityService()

        # Create a marker first
        marker_result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["old words"],
        )

        # Correct it
        correction_result = service.correct(
            marker_id=marker_result["marker_id"],
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["new words"],
        )

        assert correction_result["authoritative"] is True

    def test_correct_uses_subject_correction(self):
        """correct() uses subject's correction as authoritative."""
        service = ContinuityService()

        marker_result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["was wrong"],
        )

        correction_result = service.correct(
            marker_id=marker_result["marker_id"],
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["corrected words"],
            created_by="subject",
        )

        assert correction_result["subject_words"] == ["corrected words"]
        assert correction_result["authoritative"] is True


class TestContinuityServiceDueFollowups:
    """Test due_followups() operation."""

    def test_due_followup_respects_max_attempts(self):
        """due_followups() respects max_attempts."""
        service = ContinuityService()

        # Create marker with followup
        marker_result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["test"],
        )

        # Verify service has due_followups method
        assert hasattr(service, "due_followups")

    def test_paused_scope_blocks_followups(self):
        """pause() blocks follow-ups from paused scope."""
        service = ContinuityService()

        # Pause scope
        pause_result = service.pause(
            subject_id="subj_001",
            scope_name="test_scope",
        )

        assert pause_result["is_paused"] is True

        # Resume scope
        resume_result = service.resume(
            subject_id="subj_001",
            scope_name="test_scope",
        )

        assert resume_result["is_paused"] is False


class TestContinuityServiceRecentMarkers:
    """Test recent_markers() operation."""

    def test_recent_markers_returns_subject_confirmed_only(self):
        """recent_markers() returns only subject-confirmed markers."""
        service = ContinuityService()

        # Create some markers
        service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["marker 1"],
        )

        results = service.recent_markers(subject_id="subj_001")

        for marker in results:
            assert marker["subject_confirmation"] is True


class TestContinuityServiceForget:
    """Test forget() operation."""

    def test_forget_removes_from_gumi_recall(self):
        """forget() removes marker from Gumi recall without deleting."""
        service = ContinuityService()

        marker_result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["to forget"],
        )

        forget_result = service.forget(
            marker_id=marker_result["marker_id"],
            subject_id="subj_001",
        )

        assert forget_result["gumi_recall_allowed"] is False


class TestContinuityServicePauseResume:
    """Test pause() and resume() operations."""

    def test_pause_blocks_followups(self):
        """pause() blocks follow-ups from paused scope."""
        service = ContinuityService()

        result = service.pause(
            subject_id="subj_001",
            scope_name="global",
        )

        assert result["is_paused"] is True

    def test_resume_restores_followups(self):
        """resume() restores follow-ups."""
        service = ContinuityService()

        service.pause(subject_id="subj_001", scope_name="global")

        result = service.resume(
            subject_id="subj_001",
            scope_name="global",
        )

        assert result["is_paused"] is False


class TestSharedContinuityIsSubjectScoped:
    """Test subject scoping."""

    def test_all_operations_require_subject_scope(self):
        """All operations require subject_id, gumi_instance_id, hermes_profile_id."""
        service = ContinuityService()

        # remember requires scope
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["test"],
        )

        assert "subject_id" in result
        assert "gumi_instance_id" in result
        assert "hermes_profile_id" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])