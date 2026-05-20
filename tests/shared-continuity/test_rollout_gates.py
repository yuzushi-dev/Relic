"""
PR33I — Rollout Gates Tests

Tests for rollout gates:
- Subject confirmation required before marker storage
- No clinical terms in any context
- Scope enforcement on all operations
"""

import pytest
from relic.shared_continuity.service import ContinuityService, FORBIDDEN_CLINICAL_TERMS


class TestRolloutGates:
    """Test rollout gates for Shared Continuity Memory."""

    @pytest.fixture
    def service(self):
        return ContinuityService()

    def test_rollout_gate_subject_confirmation_required(self, service):
        """Rollout gate: subject confirmation required."""
        result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["test"],
            subject_confirmation=True,
        )

        assert result["subject_confirmation"] is True

    def test_rollout_gate_no_clinical_in_context(self, service):
        """Rollout gate: no clinical terms in context."""
        service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["clean words"],
            subject_confirmation=True,
        )

        markers = service.recent_markers(subject_id="subj_001")
        markers_str = str(markers).lower()

        for term in FORBIDDEN_CLINICAL_TERMS:
            assert term not in markers_str

    def test_rollout_gate_scope_enforcement(self, service):
        """Rollout gate: scope enforcement."""
        service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["scope test"],
            subject_confirmation=True,
        )

        # Get markers for different subject
        markers = service.recent_markers(subject_id="subj_002")

        # Should return empty or only subj_002 markers
        for marker in markers:
            assert marker["subject_id"] == "subj_002"

    def test_rollout_gate_pause_resume(self, service):
        """Rollout gate: pause/resume works correctly."""
        pause_result = service.pause(
            subject_id="subj_001",
            scope_name="global",
        )

        assert pause_result["is_paused"] is True

        resume_result = service.resume(
            subject_id="subj_001",
            scope_name="global",
        )

        assert resume_result["is_paused"] is False

    def test_rollout_gate_forget_removes_recall(self, service):
        """Rollout gate: forget removes from Gumi recall."""
        marker = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["to forget"],
            subject_confirmation=True,
        )

        forget_result = service.forget(
            marker_id=marker["marker_id"],
            subject_id="subj_001",
        )

        assert forget_result["gumi_recall_allowed"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])