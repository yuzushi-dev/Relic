"""Tests for scope adjustment and compile gate.

Acceptance criteria:
- feedback propagation marks affected artifacts stale
- S2 warnings are hidden or batchable only when non-runtime-impacting

Block conditions checked:
- feedback affects runtime before compiler rerun
- UI can edit compiled artifacts directly
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from relic.ui.audit import (
    BatchReleasePolicy,
    ExceptionWorkbenchDefaults,
    RiskSeverity,
)
from relic.ui.feedback import (
    FeedbackProcessor,
    FeedbackPropagationMode,
    ResearcherFeedbackAction,
)


class TestScopeAdjustmentRecompile:
    """Tests for scope adjustment with compile gate enforcement."""

    def test_scope_adjust_marks_artifacts_stale(self):
        """SCOPE_ADJUST marks affected artifacts as stale."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        artifact_ids = [uuid4(), uuid4()]
        
        event = processor.scope_adjust(
            target_id=target_id,
            target_type="prompt_record",
            new_scope="restricted",
            affected_artifact_ids=artifact_ids,
        )
        
        assert event.marked_stale is True
        assert event.affected_artifact_ids == artifact_ids
        assert event.propagation_mode == FeedbackPropagationMode.MARKS_STALE

    def test_scope_adjust_has_runtime_impact_pending_compile(self):
        """Scope adjustment has runtime impact requiring compile gate."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.scope_adjust(
            target_id=target_id,
            target_type="prompt_record",
            new_scope="restricted",
            runtime_impact="medium",
        )
        
        # Runtime impact is pending until compile completes
        assert event.runtime_impact_pending_compile is True
        assert event.runtime_impact == "medium"
        # BLOCK: feedback cannot affect runtime before compiler rerun

    def test_scope_adjust_triggers_recompile_gate(self):
        """Scope adjustment requires recompile before runtime."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        artifact_ids = [uuid4()]
        
        event = processor.scope_adjust(
            target_id=target_id,
            target_type="prompt_record",
            new_scope="narrowed",
            affected_artifact_ids=artifact_ids,
            runtime_impact="high",
        )
        
        # Event is created but flagged for compile
        assert event.action == ResearcherFeedbackAction.SCOPE_ADJUST
        assert event.runtime_impact_pending_compile is True
        # UI cannot apply this to runtime until compile completes

    def test_s2_batchable_only_when_non_runtime(self):
        """S2 warnings are batchable only when non-runtime-impacting.
        
        BLOCK: S2 warnings are batchable only when non-runtime-impacting
        """
        # S2 runtime-impacting cannot batch
        assert ExceptionWorkbenchDefaults.can_batch_release(
            RiskSeverity.S2,
            states=["stale"],
            runtime_impacting=True,
        ) is False
        
        # S2 non-runtime-impacting can batch
        assert ExceptionWorkbenchDefaults.can_batch_release(
            RiskSeverity.S2,
            states=["pending"],
            runtime_impacting=False,
        ) is True

    def test_s0_cannot_batch_release(self):
        """S0 items cannot be batch-released.
        
        BLOCK: S0 or S1 items can be batch-released
        """
        assert ExceptionWorkbenchDefaults.can_batch_release(
            RiskSeverity.S0,
            states=[],
            runtime_impacting=False,
        ) is False
        
        assert ExceptionWorkbenchDefaults.can_batch_release(
            RiskSeverity.S0,
            states=[],
            runtime_impacting=True,
        ) is False

    def test_s1_cannot_batch_release(self):
        """S1 items cannot be batch-released."""
        assert ExceptionWorkbenchDefaults.can_batch_release(
            RiskSeverity.S1,
            states=[],
            runtime_impacting=False,
        ) is False
        
        assert ExceptionWorkbenchDefaults.can_batch_release(
            RiskSeverity.S1,
            states=[],
            runtime_impacting=True,
        ) is False

    def test_runtime_impacting_states_block_batch(self):
        """Runtime-impacting states block batch release."""
        defaults = ExceptionWorkbenchDefaults()
        
        # Any S0/S1 with runtime-impacting state
        assert defaults.can_batch_release(
            RiskSeverity.S0,
            states=["disputed"],
            runtime_impacting=True,
        ) is False
        
        assert defaults.can_batch_release(
            RiskSeverity.S1,
            states=["sensitive"],
            runtime_impacting=True,
        ) is False


class TestCompileGate:
    """Tests for compile gate enforcement."""

    def test_feedback_with_runtime_impact_pending_compile(self):
        """Feedback with runtime impact is pending compile."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        for impact_level in ["low", "medium", "high"]:
            event = processor.validate(
                target_id=target_id,
                target_type="prompt_record",
                runtime_impact=impact_level,
            )
            
            assert event.runtime_impact_pending_compile is True
            # BLOCK: cannot affect runtime before compile

    def test_feedback_without_runtime_impact_no_pending(self):
        """Feedback without runtime impact doesn't need compile."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            runtime_impact="none",
        )
        
        assert event.runtime_impact_pending_compile is False

    def test_suppressed_feedback_no_runtime_impact(self):
        """Suppressed feedback cannot have runtime impact."""
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        event = processor.validate(
            target_id=target_id,
            target_type="prompt_record",
            subject_user_correction_exists=True,
            runtime_impact="high",
        )
        
        # Suppressed so no runtime impact
        assert event.runtime_impact_pending_compile is False


class TestBatchReleasePolicies:
    """Tests for batch release policy enforcement."""

    def test_s0_policy_never(self):
        """S0 always has NEVER policy."""
        policy = ExceptionWorkbenchDefaults().batch_release_policy[RiskSeverity.S0.value]
        assert policy == BatchReleasePolicy.NEVER

    def test_s1_policy_never(self):
        """S1 always has NEVER policy."""
        policy = ExceptionWorkbenchDefaults().batch_release_policy[RiskSeverity.S1.value]
        assert policy == BatchReleasePolicy.NEVER

    def test_s2_policy_batchable_non_runtime(self):
        """S2 has BATCHABLE_NON_RUNTIME policy."""
        policy = ExceptionWorkbenchDefaults().batch_release_policy[RiskSeverity.S2.value]
        assert policy == BatchReleasePolicy.BATCHABLE_NON_RUNTIME

    def test_s3_policy_batchable(self):
        """S3 has BATCHABLE policy."""
        policy = ExceptionWorkbenchDefaults().batch_release_policy[RiskSeverity.S3.value]
        assert policy == BatchReleasePolicy.BATCHABLE

    def test_ui_cannot_edit_compiled_artifacts(self):
        """Feedback cannot directly edit compiled artifacts.
        
        BLOCK: UI can edit compiled artifacts directly
        """
        processor = FeedbackProcessor()
        target_id = uuid4()
        
        # All feedback actions only mark stale, never modify
        event = processor.validate(
            target_id=target_id,
            target_type="compiled_artifact",
        )
        
        # Events never directly modify - only mark stale
        assert event.marked_stale is True
        assert event.propagation_mode == FeedbackPropagationMode.MARKS_STALE
        # Modification happens through compile, not direct edit
