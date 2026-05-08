"""
PR33I — Complete Integration Tests

Complete integration tests for Shared Continuity Memory:
- All PR33A-H tests included in full suite
- End-to-end flow works correctly
- No clinical terms leak through
"""

import sys
from pathlib import Path

# Ensure repo root is in sys.path so hermes_plugin wrapper resolves
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from relic.shared_continuity.service import ContinuityService, FORBIDDEN_CLINICAL_TERMS
from relic.shared_continuity.followup_lifecycle import FollowupLifecycle
from hermes_plugin.tools.relic_shared_continuity import get_shared_continuity_tools
from hermes_plugin.hooks.shared_continuity import get_shared_continuity_hooks


class TestCompleteIntegration:
    """Complete integration tests for Shared Continuity Memory."""

    @pytest.fixture
    def service(self):
        return ContinuityService()

    @pytest.fixture
    def lifecycle(self):
        return FollowupLifecycle()

    @pytest.fixture
    def tools(self):
        return get_shared_continuity_tools()

    @pytest.fixture
    def hooks(self):
        return get_shared_continuity_hooks()

    def test_end_to_end_marker_lifecycle(self, service):
        """End-to-end marker lifecycle works correctly."""
        # Create marker
        marker = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["end to end test"],
        )

        assert marker["subject_confirmation"] is True
        assert marker["status"] == "active"

        # Get recent markers
        markers = service.recent_markers(subject_id="subj_001")
        assert len(markers) >= 1

        # Correct marker
        correction = service.correct(
            marker_id=marker["marker_id"],
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["corrected test"],
        )

        assert correction["authoritative"] is True

    def test_no_clinical_terms_in_any_output(self, service, hooks):
        """No clinical terms leak through any output."""
        # Create marker
        service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["clean words"],
        )

        # Get recent markers
        markers = service.recent_markers(subject_id="subj_001")

        # Check hooks output
        hook_result = hooks.pre_llm_call(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        all_output = str(markers) + str(hook_result)

        for term in FORBIDDEN_CLINICAL_TERMS:
            assert term not in all_output.lower()

    def test_subject_scope_isolates_data(self, service):
        """Subject scope correctly isolates data between subjects."""
        # Create markers for two subjects
        service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["subj_001 marker"],
        )

        service.remember(
            subject_id="subj_002",
            gumi_instance_id="gumi_002",
            hermes_profile_id="hermes_002",
            subject_words=["subj_002 marker"],
        )

        # Get markers for subj_001
        markers_subj1 = service.recent_markers(subject_id="subj_001")

        # Get markers for subj_002
        markers_subj2 = service.recent_markers(subject_id="subj_002")

        # Verify isolation
        for marker in markers_subj1:
            assert marker["subject_id"] == "subj_001"

        for marker in markers_subj2:
            assert marker["subject_id"] == "subj_002"

    def test_followup_lifecycle_complete(self, lifecycle):
        """Followup lifecycle completes correctly."""
        # Create followup
        followup = lifecycle.create_followup(
            followup_id="fu_complete",
            marker_id="marker_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            max_attempts=3,
        )

        assert followup.max_attempts == 3
        assert followup.attempt_count == 0

        # Mark as sent
        lifecycle.mark_sent("fu_complete")
        assert lifecycle._followups["fu_complete"].attempt_count == 1

        # Mark as acknowledged
        lifecycle.mark_acknowledged("fu_complete")
        assert lifecycle._followups["fu_complete"].status.value == "acknowledged"

    def test_tools_work_correctly(self, tools):
        """Plugin tools work correctly."""
        # Remember marker
        marker = tools.tool_remember_marker(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["tool test"],
        )

        assert marker["subject_confirmation"] is True

        # Get recent markers
        markers = tools.tool_get_recent_markers(subject_id="subj_001")
        assert isinstance(markers, list)

    def test_hooks_filter_correctly(self, hooks):
        """Hooks filter markers correctly."""
        result = hooks.pre_llm_call(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        assert "shared_continuity_markers" in result
        assert "marker_count" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])