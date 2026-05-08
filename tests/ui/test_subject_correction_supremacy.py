"""Tests for subject_user correction supremacy.

Acceptance criteria:
- subject_user correction always outranks researcher validation

Block conditions checked:
- researcher validation overrides subject_user correction (BLOCK)
- feedback affects runtime before compiler rerun
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from relic.ui.feedback import (
    FeedbackProcessor,
    ResearcherFeedbackAction,
    SubjectCorrectionSupremacy,
)


class TestSubjectCorrectionSupremacy:
    """Tests for subject_user correction supremacy enforcement."""

    def test_validate_suppressed_by_subject_correction(self):
        """VALIDATE is suppressed when subject_user correction exists.
        
        BLOCK: researcher validation overrides subject_user correction
        """
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        # When subject_user has already corrected
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            subject_user_correction_exists=True,
            rationale="Researcher validation",
        )
        
        # Researcher validation should be suppressed
        assert event.subject_user_correction_suppresses_researcher is True
        assert event.action == ResearcherFeedbackAction.REQUEST_CLARIFICATION
        assert event.subject_user_correction_applied is True

    def test_reject_suppressed_by_subject_correction(self):
        """REJECT is suppressed when subject_user correction exists."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.reject(
            target_id=target_id,
            target_type="prompt_record",
            subject_user_correction_exists=True,
            rationale="Researcher rejection",
        )
        
        assert event.subject_user_correction_suppresses_researcher is True
        assert event.action == ResearcherFeedbackAction.REQUEST_CLARIFICATION

    def test_scope_adjust_suppressed_by_subject_correction(self):
        """SCOPE_ADJUST is suppressed when subject_user correction exists."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.scope_adjust(
            target_id=target_id,
            target_type="prompt_record",
            new_scope="restricted",
            subject_user_correction_exists=True,
            rationale="Researcher scope change",
        )
        
        assert event.subject_user_correction_suppresses_researcher is True
        assert event.action == ResearcherFeedbackAction.REQUEST_CLARIFICATION

    def test_mark_sensitive_not_suppressed(self):
        """MARK_SENSITIVE is NOT suppressed - privacy gate override."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        # Even with subject_user correction, privacy gate triggers
        event = processor.mark_sensitive(
            target_id=target_id,
            target_type="prompt_record",
            rationale="Privacy gate override",
        )
        
        # Not suppressed because it triggers privacy review
        assert event.subject_user_correction_suppresses_researcher is False
        assert event.triggered_privacy_review is True

    def test_create_eval_case_not_suppressed(self):
        """CREATE_EVAL_CASE is NOT suppressed - evaluation purposes."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.create_eval_case(
            target_id=target_id,
            target_type="artifact",
            rationale="Regression test case",
        )
        
        assert event.subject_user_correction_suppresses_researcher is False

    def test_suppressed_feedback_marks_no_artifacts_stale(self):
        """Suppressed feedback does not mark artifacts stale."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        artifact_ids = [uuid4()]
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            subject_user_correction_exists=True,
            affected_artifact_ids=artifact_ids,
        )
        
        # Suppressed feedback doesn't propagate
        assert event.marked_stale is False
        assert event.propagation_mode.value == "none"

    def test_suppressed_feedback_has_no_runtime_impact(self):
        """Suppressed feedback cannot have runtime impact."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            subject_user_correction_exists=True,
            runtime_impact="high",
        )
        
        # Suppressed feedback cannot impact runtime
        assert event.runtime_impact_pending_compile is False

    def test_non_suppressed_feedback_marks_stale(self):
        """Non-suppressed feedback marks artifacts stale."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        artifact_ids = [uuid4()]
        
        # Without subject_user correction
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            subject_user_correction_exists=False,
            affected_artifact_ids=artifact_ids,
        )
        
        assert event.marked_stale is True
        assert event.propagation_mode.value == "marks_stale"


class TestSupremacyLogic:
    """Unit tests for SubjectCorrectionSupremacy logic."""

    def test_is_researcher_suppressed_validate(self):
        """VALIDATE is suppressed by subject_user correction."""
        assert SubjectCorrectionSupremacy.is_researcher_suppressed(
            subject_user_correction_exists=True,
            researcher_action=ResearcherFeedbackAction.VALIDATE,
        ) is True

    def test_is_researcher_suppressed_reject(self):
        """REJECT is suppressed by subject_user correction."""
        assert SubjectCorrectionSupremacy.is_researcher_suppressed(
            subject_user_correction_exists=True,
            researcher_action=ResearcherFeedbackAction.REJECT,
        ) is True

    def test_is_researcher_suppressed_scope_adjust(self):
        """SCOPE_ADJUST is suppressed by subject_user correction."""
        assert SubjectCorrectionSupremacy.is_researcher_suppressed(
            subject_user_correction_exists=True,
            researcher_action=ResearcherFeedbackAction.SCOPE_ADJUST,
        ) is True

    def test_is_researcher_suppressed_mark_sensitive(self):
        """MARK_SENSITIVE is NOT suppressed."""
        assert SubjectCorrectionSupremacy.is_researcher_suppressed(
            subject_user_correction_exists=True,
            researcher_action=ResearcherFeedbackAction.MARK_SENSITIVE,
        ) is False

    def test_is_researcher_suppressed_create_eval_case(self):
        """CREATE_EVAL_CASE is NOT suppressed."""
        assert SubjectCorrectionSupremacy.is_researcher_suppressed(
            subject_user_correction_exists=True,
            researcher_action=ResearcherFeedbackAction.CREATE_EVAL_CASE,
        ) is False

    def test_no_correction_no_suppression(self):
        """No subject_user correction means no suppression."""
        for action in ResearcherFeedbackAction:
            assert SubjectCorrectionSupremacy.is_researcher_suppressed(
                subject_user_correction_exists=False,
                researcher_action=action,
            ) is False

    def test_get_effective_action_suppressed(self):
        """Suppressed action becomes REQUEST_CLARIFICATION."""
        result = SubjectCorrectionSupremacy.get_effective_action(
            researcher_action=ResearcherFeedbackAction.VALIDATE,
            suppressed=True,
        )
        assert result == ResearcherFeedbackAction.REQUEST_CLARIFICATION

    def test_get_effective_action_not_suppressed(self):
        """Non-suppressed action remains unchanged."""
        result = SubjectCorrectionSupremacy.get_effective_action(
            researcher_action=ResearcherFeedbackAction.VALIDATE,
            suppressed=False,
        )
        assert result == ResearcherFeedbackAction.VALIDATE
