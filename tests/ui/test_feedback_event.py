"""Tests for researcher feedback event production.

Acceptance criteria:
- validate/reject/scope_adjust/mark_sensitive/create_eval_case produce researcher_feedback_event

Block conditions checked:
- researcher validation overrides subject_user correction
- feedback affects runtime before compiler rerun
- UI persists raw final prompts
- UI trace lacks actor_role or target_id
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from relic.ui.feedback import (
    FeedbackProcessor,
    ResearcherFeedbackAction,
    ResearcherFeedbackEvent,
)


class TestFeedbackEventProduction:
    """Tests that every action produces researcher_feedback_event."""

    def test_validate_produces_event(self):
        """VALIDATE action produces researcher_feedback_event."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            rationale="Looks correct",
        )
        
        assert isinstance(event, ResearcherFeedbackEvent)
        assert event.action == ResearcherFeedbackAction.VALIDATE
        assert event.target_id == target_id
        assert event.actor_role == "researcher"

    def test_reject_produces_event(self):
        """REJECT action produces researcher_feedback_event."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.reject(
            target_id=target_id,
            target_type="prompt_record",
            rationale="Contains policy violation",
        )
        
        assert isinstance(event, ResearcherFeedbackEvent)
        assert event.action == ResearcherFeedbackAction.REJECT
        assert event.target_id == target_id

    def test_scope_adjust_produces_event(self):
        """SCOPE_ADJUST action produces researcher_feedback_event."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.scope_adjust(
            target_id=target_id,
            target_type="eval_case",
            new_scope="restricted",
            rationale="Narrowing scope for safety",
        )
        
        assert isinstance(event, ResearcherFeedbackEvent)
        assert event.action == ResearcherFeedbackAction.SCOPE_ADJUST
        assert event.new_scope == "restricted"
        assert event.target_id == target_id

    def test_mark_sensitive_produces_event(self):
        """MARK_SENSITIVE action produces researcher_feedback_event."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.mark_sensitive(
            target_id=target_id,
            target_type="prompt_record",
            rationale="Contains PII",
        )
        
        assert isinstance(event, ResearcherFeedbackEvent)
        assert event.action == ResearcherFeedbackAction.MARK_SENSITIVE
        assert event.triggered_privacy_review is True  # Always triggers privacy review
        assert event.target_id == target_id

    def test_create_eval_case_produces_event(self):
        """CREATE_EVAL_CASE action produces researcher_feedback_event."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.create_eval_case(
            target_id=target_id,
            target_type="artifact",
            rationale="This is a regression case",
            delta_content="expected_correction",
        )
        
        assert isinstance(event, ResearcherFeedbackEvent)
        assert event.action == ResearcherFeedbackAction.CREATE_EVAL_CASE
        assert event.target_id == target_id

    def test_event_has_required_fields(self):
        """Event must have actor_role and target_id - BLOCK if missing."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
        )
        
        # Block condition: UI trace lacks actor_role or target_id
        assert event.actor_role is not None
        assert event.actor_role != ""
        assert event.target_id is not None
        assert event.target_id == target_id

    def test_feedback_marks_artifacts_stale(self):
        """Feedback propagation marks affected artifacts stale."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        artifact_ids = [uuid4(), uuid4()]
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            affected_artifact_ids=artifact_ids,
        )
        
        assert event.marked_stale is True
        assert event.affected_artifact_ids == artifact_ids
        assert event.propagation_mode.value == "marks_stale"

    def test_runtime_impact_tracked(self):
        """Runtime impact is tracked but cannot bypass compile gate."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            runtime_impact="high",
        )
        
        # Runtime impact is tracked
        assert event.runtime_impact == "high"
        # But runtime_impact_pending_compile is True (requires compile)
        assert event.runtime_impact_pending_compile is True

    def test_no_raw_prompts_in_event(self):
        """Events must not contain raw final prompts."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            rationale="Review of content hash abc123",
        )
        
        # Event should be serializable without raw data
        data = event.model_dump_json_safe()
        assert isinstance(data, dict)
        # Rationale should not contain actual prompt content
        assert "abc123" not in event.rationale or event.rationale == ""
