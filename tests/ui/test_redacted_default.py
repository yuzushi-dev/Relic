"""Tests for redacted-by-default behavior in UI view models.

These tests verify that:
- Every view model is redacted by default
- Every visible claim contains lineage_refs and review_status
- UI implements exception-workbench defaults for runtime-impacting items
- S0/S1 items cannot be batch-released
- State is NOT represented through color only
- UI trace has actor_role and target_id
- Sensitive mark triggers privacy review
"""

import json
from datetime import datetime
from uuid import uuid4

import pytest

from relic.ui.contracts import (
    ExceptionWorkbenchDefaults,
    LineageRef,
    REDACTED_PLACEHOLDER,
    ReviewBurdenMetrics,
    ResearcherFeedbackEvent,
    ReviewBurdenMetrics,
    ReviewQueueItem,
    ReviewStatus,
    RiskLevel,
    UI_STATE_DESCRIPTIONS,
    UI_STATE_ENUM,
)
from relic.ui.view_models import (
    AuditDashboardViewModel,
    REDACTED_PLACEHOLDER,
    ReviewItemViewModel,
    ReviewQueueViewModel,
    ViewModelBase,
    validate_design,
)


class TestRedactedByDefault:
    """Test that all view models are redacted by default."""

    def test_review_queue_item_is_redacted_by_default(self):
        """Verify ReviewQueueItem is redacted by default."""
        item = ReviewQueueItem(
            content_hash="abc123",
            lineage_refs=[],
        )
        assert item.is_content_redacted is True, "ReviewQueueItem must be redacted by default"

    def test_review_item_view_model_is_redacted_by_default(self):
        """Verify ReviewItemViewModel shows redacted content."""
        # Create underlying item
        item = ReviewQueueItem(
            item_id=uuid4(),
            content_hash="test_hash_123",
            lineage_refs=[],
            review_status=ReviewStatus.PENDING,
        )
        
        vm = ReviewItemViewModel.from_item(item)
        assert vm.is_content_redacted is True, "ReviewItemViewModel must show redacted content by default"

    def test_researcher_feedback_is_redacted_by_default(self):
        """Verify ResearcherFeedbackEvent is redacted by default."""
        event = ResearcherFeedbackEvent(
            feedback_type="correction",
            severity="major",
            target_id=uuid4(),
            actor_role="researcher",
            lineage_refs=[],
        )
        assert event.is_feedback_redacted is True, "ResearcherFeedbackEvent must be redacted by default"


class TestLineageRefsRequired:
    """Test that every visible claim contains lineage_refs and review_status."""

    def test_review_queue_item_requires_lineage_refs(self):
        """Verify ReviewQueueItem has lineage_refs field."""
        item = ReviewQueueItem(
            content_hash="abc123",
            lineage_refs=[],
        )
        assert hasattr(item, "lineage_refs"), "ReviewQueueItem must have lineage_refs"
        assert isinstance(item.lineage_refs, list), "lineage_refs must be a list"

    def test_review_item_view_model_preserves_lineage_refs(self):
        """Verify ReviewItemViewModel preserves lineage_refs from underlying item."""
        lineage_ref = LineageRef(
            artifact_id=uuid4(),
            artifact_type="runtime_profile",
            relationship="derived_from",
        )
        
        item = ReviewQueueItem(
            item_id=uuid4(),
            content_hash="test_hash",
            lineage_refs=[lineage_ref],
            review_status=ReviewStatus.PENDING,
        )
        
        vm = ReviewItemViewModel.from_item(item)
        assert len(vm.lineage_refs) == 1, "ReviewItemViewModel must preserve lineage_refs"
        assert vm.lineage_refs[0].artifact_id == lineage_ref.artifact_id

    def test_researcher_feedback_requires_lineage_refs(self):
        """Verify ResearcherFeedbackEvent has lineage_refs and validates."""
        event = ResearcherFeedbackEvent(
            feedback_type="correction",
            severity="major",
            target_id=uuid4(),
            actor_role="researcher",
            lineage_refs=[],  # Empty lineage
        )
        
        is_valid, errors = event.validate()
        assert is_valid is False, "Feedback without lineage_refs must be invalid"
        assert "feedback_requires_lineage_refs" in errors


class TestReviewStatusRequired:
    """Test that review_status is required for all visible claims."""

    def test_review_queue_item_has_review_status(self):
        """Verify ReviewQueueItem has review_status field."""
        item = ReviewQueueItem(
            content_hash="abc123",
            lineage_refs=[],
        )
        assert hasattr(item, "review_status"), "ReviewQueueItem must have review_status"
        assert isinstance(item.review_status, ReviewStatus)

    def test_view_model_preserves_review_status(self):
        """Verify view models preserve review_status."""
        item = ReviewQueueItem(
            item_id=uuid4(),
            content_hash="test_hash",
            lineage_refs=[],
            review_status=ReviewStatus.UNDER_REVIEW,
        )
        
        vm = ReviewItemViewModel.from_item(item)
        assert vm.review_status == ReviewStatus.UNDER_REVIEW


class TestExceptionWorkbenchDefaults:
    """Test exception-workbench defaults for runtime-impacting items."""

    def test_disputed_item_defaults_to_high_risk(self):
        """Disputed items should default to S1 risk level."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            is_disputed=True,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.risk_level == RiskLevel.S1_HIGH_RISK

    def test_sensitive_item_triggers_escalation(self):
        """Sensitive items should trigger privacy review."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            is_sensitive=True,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.review_status == ReviewStatus.ESCALATED

    def test_stale_item_can_batch_if_not_runtime_impacting(self):
        """Stale items can batch only when non-runtime-impacting."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            is_stale=True,
            is_runtime_impacting=False,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.can_batch_release is True

    def test_uncertain_item_cannot_batch(self):
        """Uncertain items cannot be batch-released."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            is_uncertain=True,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.can_batch_release is False


class TestBatchReleaseRules:
    """Test that S0/S1 items cannot be batch-released."""

    def test_s0_cannot_batch_release(self):
        """S0 items cannot be batch-released."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            risk_level=RiskLevel.S0_HARD_VIOLATION,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.can_batch_release is False

    def test_s1_cannot_batch_release(self):
        """S1 items cannot be batch-released."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            risk_level=RiskLevel.S1_HIGH_RISK,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.can_batch_release is False

    def test_s2_can_batch_if_not_runtime_impacting(self):
        """S2 items can batch only when non-runtime-impacting."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            risk_level=RiskLevel.S2_WARNING,
            is_runtime_impacting=False,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.can_batch_release is True

    def test_s2_cannot_batch_if_runtime_impacting(self):
        """S2 runtime-impacting items cannot batch."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            risk_level=RiskLevel.S2_WARNING,
            is_runtime_impacting=True,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.can_batch_release is False


class TestStateRepresentationNotColorOnly:
    """Test that state is NOT represented through color only."""

    def test_ui_state_descriptions_exist(self):
        """Verify UI_STATE_DESCRIPTIONS is populated."""
        assert len(UI_STATE_DESCRIPTIONS) > 0
        assert all(isinstance(v, str) and len(v) > 0 for v in UI_STATE_DESCRIPTIONS.values())

    def test_review_item_provides_text_state(self):
        """ReviewItemViewModel provides descriptive state text."""
        item = ReviewQueueItem(
            item_id=uuid4(),
            content_hash="test_hash",
            lineage_refs=[],
            is_disputed=True,
        )
        
        vm = ReviewItemViewModel.from_item(item)
        state = vm.get_display_state()
        
        # State must be descriptive text, not just a color code
        assert isinstance(state, str)
        assert len(state) > 0
        assert "Content has conflicting claims" in state or "disputed" in state.lower()

    def test_review_item_provides_text_risk_indicator(self):
        """ReviewItemViewModel provides descriptive risk indicator."""
        item = ReviewQueueItem(
            item_id=uuid4(),
            content_hash="test_hash",
            lineage_refs=[],
            risk_level=RiskLevel.S1_HIGH_RISK,
        )
        
        vm = ReviewItemViewModel.from_item(item)
        indicator = vm.get_risk_indicator()
        
        # Risk indicator must be descriptive text
        assert isinstance(indicator, str)
        assert len(indicator) > 0
        assert "S1" in indicator or "risk" in indicator.lower()


class TestUITraceRequirements:
    """Test that UI traces have required actor_role and target_id."""

    def test_review_queue_item_has_actor_role(self):
        """ReviewQueueItem has actor_role field."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
        )
        assert hasattr(item, "actor_role")

    def test_review_queue_item_has_target_id(self):
        """ReviewQueueItem has target_id field."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
        )
        assert hasattr(item, "target_id")

    def test_review_item_view_model_validates_trace_requirements(self):
        """ReviewItemViewModel validates actor_role and target_id are present."""
        item = ReviewQueueItem(
            item_id=uuid4(),
            content_hash="test_hash",
            lineage_refs=[],
        )
        
        vm = ReviewItemViewModel.from_item(item)
        
        # Missing actor_role and target_id should fail validation
        is_valid, errors = vm.validate_trace_requirements()
        assert is_valid is False
        assert "UI_trace_missing_actor_role" in errors

    def test_review_item_with_trace_fields_passes_validation(self):
        """View model with actor_role and target_id passes trace validation."""
        item = ReviewQueueItem(
            item_id=uuid4(),
            content_hash="test_hash",
            lineage_refs=[],
            actor_role="researcher",
            target_id=uuid4(),
        )
        
        vm = ReviewItemViewModel.from_item(item)
        is_valid, errors = vm.validate_trace_requirements()
        assert is_valid is True


class TestSensitiveMarkTriggersPrivacyReview:
    """Test that sensitive mark triggers privacy review."""

    def test_sensitive_item_has_flag(self):
        """Sensitive items have is_sensitive flag."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            is_sensitive=True,
        )
        assert item.is_sensitive is True

    def test_sensitive_triggers_review_status_change(self):
        """Sensitive flag triggers escalation via exception workbench."""
        item = ReviewQueueItem(
            content_hash="test_hash",
            lineage_refs=[],
            is_sensitive=True,
        )
        
        applied = ExceptionWorkbenchDefaults.for_item(item)
        assert applied.review_status == ReviewStatus.ESCALATED


class TestValidateDesign:
    """Test validate_design() function."""

    def test_validate_design_passes(self):
        """validate_design() should pass with correct implementation."""
        assert validate_design() is True


class TestReviewQueueMetrics:
    """Test review burden metrics in queue view model."""

    def test_queue_view_model_calculates_metrics(self):
        """ReviewQueueViewModel should calculate metrics from items."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash1",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash2",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
                review_status=ReviewStatus.AUTO_RESOLVED,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        assert vm.metrics.total_items == 2
        assert vm.metrics.s0_count == 1
        assert vm.metrics.low_risk_count == 1

    def test_high_risk_items_not_buried(self):
        """High-risk items should appear first in sorted queue."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="low_hash",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s0_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s1_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S1_HIGH_RISK,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # First items should be S0 and S1
        high_risk = vm.get_high_risk_items()
        assert len(high_risk) == 2
        assert high_risk[0].risk_level == RiskLevel.S0_HARD_VIOLATION


class TestJSONSchemas:
    """Test that JSON schemas validate fixture examples."""

    def test_researcher_feedback_schema_validates(self):
        """ResearcherFeedbackEvent should be valid per its schema."""
        import jsonschema
        
        schema = json.loads(open("schemas/researcher_feedback_event.schema.json").read())
        
        valid_event = {
            "event_id": str(uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "feedback_type": "correction",
            "severity": "major",
            "target_id": str(uuid4()),
            "actor_role": "researcher",
            "lineage_refs": [
                {
                    "artifact_id": str(uuid4()),
                    "artifact_type": "runtime_profile",
                    "relationship": "corrects",
                    "created_at": datetime.utcnow().isoformat() + "Z"
                }
            ],
            "is_feedback_redacted": True
        }
        
        # Should not raise
        jsonschema.validate(valid_event, schema)

    def test_ui_review_status_schema_validates(self):
        """UI review status should be valid per its schema."""
        import jsonschema
        
        schema = json.loads(open("schemas/ui_review_status.schema.json").read())
        
        valid_item = {
            "item_id": str(uuid4()),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "content_hash": "a" * 64,
            "is_content_redacted": True,
            "lineage_refs": [],
            "review_status": "pending",
            "risk_level": "s0",
            "actor_role": "researcher",
            "target_id": str(uuid4())
        }
        
        # Should not raise
        jsonschema.validate(valid_item, schema)


class TestPrivacyGuarantees:
    """Test privacy guarantees are maintained."""

    def test_no_raw_content_in_view_model(self):
        """View models should never expose raw content."""
        item = ReviewQueueItem(
            item_id=uuid4(),
            content_hash="secure_hash_abc",
            lineage_refs=[],
        )
        
        vm = ReviewItemViewModel.from_item(item)
        
        # Content hash is stored, but actual content is never exposed
        assert vm.content_hash == "secure_hash_abc"
        # No way to get original content from view model
        assert not hasattr(vm, "content") or getattr(vm, "content", None) is None

    def test_redacted_placeholder_is_correct(self):
        """REDACTED_PLACEHOLDER must be the correct value."""
        assert REDACTED_PLACEHOLDER == "[REDACTED]"
