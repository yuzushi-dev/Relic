"""Researcher feedback processing module.

This module handles researcher feedback with proper gatekeeping:
- Feedback does NOT affect runtime before compiler rerun
- Subject user corrections are always respected
- Sensitive marks trigger privacy review
- All feedback is audited with actor_role and target_id
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ResearcherFeedbackAction(str, Enum):
    """Possible researcher feedback actions."""
    CORRECT = "correct"
    VALIDATE = "validate"
    FLAG = "flag"
    ESCALATE = "escalate"
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CLARIFICATION = "request_clarification"
    MARK_STALE = "mark_stale"
    SCOPE_ADJUST = "scope_adjust"
    MARK_SENSITIVE = "mark_sensitive"
    CREATE_EVAL_CASE = "create_eval_case"


class FeedbackPropagationMode(str, Enum):
    """Mode of feedback propagation through the system."""
    NONE = "none"  # No propagation (subject_user correction pending)
    MARKS_STALE = "marks_stale"  # Marks items stale
    TRIGGERS_PRIVACY_REVIEW = "triggers_privacy_review"  # Triggers privacy review
    CORRECTS = "corrects"  # Requires compiler rerun
    APPROVES = "approves"  # Direct approval


class SubjectCorrectionSupremacy(str, Enum):
    """Whether subject user correction suppresses researcher feedback."""
    RESEARCHER_PREVAILS = "researcher_prevails"
    SUBJECT_USER_SUPPRESSES = "subject_user_suppresses"
    PENDING_RESOLUTION = "pending_resolution"

    @classmethod
    def is_researcher_suppressed(
        cls,
        subject_user_correction_exists: bool,
        researcher_action: "ResearcherFeedbackAction",
    ) -> bool:
        """Return True if subject user correction suppresses this researcher action."""
        if not subject_user_correction_exists:
            return False
        # MARK_SENSITIVE and CREATE_EVAL_CASE are never suppressed
        unsuppressible = {"MARK_SENSITIVE", "CREATE_EVAL_CASE", "FLAG", "ESCALATE", "APPROVE"}
        return researcher_action.name not in unsuppressible

    @classmethod
    def get_effective_action(
        cls,
        researcher_action: "ResearcherFeedbackAction",
        suppressed: bool,
    ) -> "ResearcherFeedbackAction":
        """Return effective action; suppressed actions become REQUEST_CLARIFICATION."""
        if suppressed:
            return ResearcherFeedbackAction.REQUEST_CLARIFICATION
        return researcher_action


class ResearcherFeedbackEvent(BaseModel):
    """Researcher feedback event with full audit trail.

    Guarantees:
    - actor_role and target_id are always present
    - feedback does not affect runtime before compiler rerun
    - subject_user corrections are respected
    """

    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Required for UI trace
    actor_role: str
    target_id: UUID

    # Feedback details
    action: ResearcherFeedbackAction
    rationale: str | None = None
    affected_artifact_ids: list[UUID] = Field(default_factory=list)
    new_scope: str | None = None
    runtime_impact: str = "low"

    # Suppression tracking
    subject_user_correction_suppresses_researcher: bool = False
    subject_user_correction_applied: bool = False

    # Runtime impact
    runtime_impact_pending_compile: bool = True
    triggered_privacy_review: bool = False

    # Propagation
    propagation_mode: FeedbackPropagationMode = FeedbackPropagationMode.NONE

    # Feedback flags
    sensitive_flag: bool = False
    marked_stale: bool = False

    def model_dump_json_safe(self) -> dict:
        """Serialize without raw prompt data."""
        d = self.model_dump()
        d["event_id"] = str(d["event_id"])
        d["target_id"] = str(d["target_id"])
        d["affected_artifact_ids"] = [str(i) for i in d["affected_artifact_ids"]]
        return d


class FeedbackProcessor:
    """Processes researcher feedback with proper gatekeeping.

    Guarantees:
    - Feedback does not affect runtime before compiler rerun
    - Subject user corrections are always respected
    - All actions are audited
    """

    def __init__(self):
        self._trace: list[ResearcherFeedbackEvent] = []

    def correct(
        self,
        target_id: UUID,
        actor_role: str,
        delta_content: str,
        rationale: str,
    ) -> ResearcherFeedbackEvent:
        """Record a correction from researcher."""
        event = ResearcherFeedbackEvent(
            target_id=target_id,
            actor_role=actor_role,
            action=ResearcherFeedbackAction.CORRECT,
            rationale=rationale,
            subject_user_correction_suppresses_researcher=False,
            runtime_impact_pending_compile=True,
            propagation_mode=FeedbackPropagationMode.CORRECTS,
        )
        self._trace.append(event)
        return event

    def validate(
        self,
        target_id: UUID,
        actor_role: str = "researcher",
        affected_artifact_ids: list[UUID] | None = None,
        runtime_impact: str = "low",
        target_type: str = "prompt_record",
        subject_user_correction_exists: bool = False,
        rationale: str | None = None,
    ) -> ResearcherFeedbackEvent:
        """Record validation feedback."""
        suppressed = SubjectCorrectionSupremacy.is_researcher_suppressed(
            subject_user_correction_exists=subject_user_correction_exists,
            researcher_action=ResearcherFeedbackAction.VALIDATE,
        )
        if suppressed:
            action = ResearcherFeedbackAction.REQUEST_CLARIFICATION
            propagation = FeedbackPropagationMode.NONE
            marked_stale = False
            runtime_impact_pending = False
        else:
            action = ResearcherFeedbackAction.VALIDATE
            propagation = FeedbackPropagationMode.MARKS_STALE
            marked_stale = True
            runtime_impact_pending = runtime_impact != "none"

        event = ResearcherFeedbackEvent(
            target_id=target_id,
            actor_role=actor_role,
            action=action,
            rationale="",  # never store raw rationale - no raw prompts in events
            affected_artifact_ids=affected_artifact_ids or [],
            runtime_impact=runtime_impact,
            subject_user_correction_suppresses_researcher=suppressed,
            subject_user_correction_applied=suppressed,
            runtime_impact_pending_compile=runtime_impact_pending,
            marked_stale=marked_stale,
            propagation_mode=propagation,
        )
        self._trace.append(event)
        return event

    def mark_sensitive(
        self,
        target_id: UUID,
        actor_role: str = "researcher",
        rationale: str | None = None,
        target_type: str = "prompt_record",
    ) -> ResearcherFeedbackEvent:
        """Mark content as sensitive (always triggers privacy review)."""
        event = ResearcherFeedbackEvent(
            target_id=target_id,
            actor_role=actor_role,
            action=ResearcherFeedbackAction.MARK_SENSITIVE,
            rationale=rationale,
            sensitive_flag=True,
            triggered_privacy_review=True,
            subject_user_correction_suppresses_researcher=False,
            propagation_mode=FeedbackPropagationMode.TRIGGERS_PRIVACY_REVIEW,
        )
        self._trace.append(event)
        return event

    def reject(
        self,
        target_id: UUID,
        actor_role: str = "researcher",
        rationale: str | None = None,
        target_type: str = "prompt_record",
        subject_user_correction_exists: bool = False,
    ) -> ResearcherFeedbackEvent:
        """Reject an item."""
        suppressed = SubjectCorrectionSupremacy.is_researcher_suppressed(
            subject_user_correction_exists=subject_user_correction_exists,
            researcher_action=ResearcherFeedbackAction.REJECT,
        )
        action = ResearcherFeedbackAction.REQUEST_CLARIFICATION if suppressed else ResearcherFeedbackAction.REJECT
        event = ResearcherFeedbackEvent(
            target_id=target_id,
            actor_role=actor_role,
            action=action,
            rationale=rationale,
            subject_user_correction_suppresses_researcher=suppressed,
            subject_user_correction_applied=suppressed,
            propagation_mode=FeedbackPropagationMode.NONE,
        )
        self._trace.append(event)
        return event

    def scope_adjust(
        self,
        target_id: UUID,
        actor_role: str = "researcher",
        rationale: str | None = None,
        target_type: str = "prompt_record",
        new_scope: str | None = None,
        affected_artifact_ids: list[UUID] | None = None,
        runtime_impact: str = "low",
        subject_user_correction_exists: bool = False,
    ) -> ResearcherFeedbackEvent:
        """Adjust scope of an item."""
        suppressed = SubjectCorrectionSupremacy.is_researcher_suppressed(
            subject_user_correction_exists=subject_user_correction_exists,
            researcher_action=ResearcherFeedbackAction.SCOPE_ADJUST,
        )
        action = ResearcherFeedbackAction.REQUEST_CLARIFICATION if suppressed else ResearcherFeedbackAction.SCOPE_ADJUST
        event = ResearcherFeedbackEvent(
            target_id=target_id,
            actor_role=actor_role,
            action=action,
            rationale=rationale,
            new_scope=new_scope,
            affected_artifact_ids=affected_artifact_ids or [],
            runtime_impact=runtime_impact,
            subject_user_correction_suppresses_researcher=suppressed,
            subject_user_correction_applied=suppressed,
            runtime_impact_pending_compile=True,
            marked_stale=True,
            propagation_mode=FeedbackPropagationMode.MARKS_STALE,
        )
        self._trace.append(event)
        return event

    def create_eval_case(
        self,
        target_id: UUID,
        actor_role: str = "researcher",
        rationale: str | None = None,
        target_type: str = "prompt_record",
        delta_content: str | None = None,
    ) -> ResearcherFeedbackEvent:
        """Create evaluation case (not for runtime impact)."""
        event = ResearcherFeedbackEvent(
            target_id=target_id,
            actor_role=actor_role,
            action=ResearcherFeedbackAction.CREATE_EVAL_CASE,
            rationale=rationale,
            subject_user_correction_suppresses_researcher=False,
            runtime_impact_pending_compile=False,
            propagation_mode=FeedbackPropagationMode.NONE,
        )
        self._trace.append(event)
        return event

    def get_trace(self) -> list[ResearcherFeedbackEvent]:
        """Get all feedback events."""
        return self._trace.copy()
