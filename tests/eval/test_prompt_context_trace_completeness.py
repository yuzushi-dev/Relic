"""Tests for PromptContextPack trace completeness (PR09).

These tests verify that PromptContextPack traces are complete for all
roleplay scenarios and that incomplete traces block release.
"""

import pytest

from relic.eval.gumi_roleplay import (
    PromptContextCompletenessResult,
    evaluate_prompt_context_completeness,
)
from relic.eval.harness import ReleaseGateHarness, ReleaseGateStatus


class TestPromptContextCompleteness:
    """Tests for PromptContextPack completeness evaluation."""

    def test_complete_prompt_context_pack(self):
        """Complete PromptContextPack passes."""
        prompt_context = {
            "continuity_mode": "compact",
            "roleplay_level": "normal",
            "admission_decision": "allowed",
            "continuity_candidates": [],
            "admission_trace": {},
            "continuity_trace": {},
        }

        result = evaluate_prompt_context_completeness("test_1", prompt_context)

        assert result.has_trace is True
        assert result.trace_completeness == 1.0
        assert result.severity.value == "pass"

    def test_missing_required_field(self):
        """Missing required field reduces completeness."""
        prompt_context = {
            "continuity_mode": "compact",
            # Missing: roleplay_level, admission_decision
        }

        result = evaluate_prompt_context_completeness("test_1", prompt_context)

        assert result.has_trace is False
        assert result.trace_completeness < 1.0
        assert "roleplay_level" in result.missing_fields
        assert "admission_decision" in result.missing_fields

    def test_missing_optional_field_reduces_score(self):
        """Missing optional fields reduce completeness score."""
        prompt_context = {
            "continuity_mode": "compact",
            "roleplay_level": "normal",
            "admission_decision": "allowed",
            # Missing: continuity_candidates, admission_trace, continuity_trace
        }

        result = evaluate_prompt_context_completeness("test_1", prompt_context)

        assert result.trace_completeness < 1.0
        assert result.trace_completeness >= 0.7

    def test_none_prompt_context_is_s0_hard(self):
        """None PromptContextPack is S0 hard violation."""
        result = evaluate_prompt_context_completeness("test_1", None)

        assert result.has_trace is False
        assert result.trace_completeness == 0.0
        assert result.severity.value == "s0_hard"
        assert "prompt_context_pack" in result.missing_fields

    def test_empty_prompt_context_is_s0_hard(self):
        """Empty PromptContextPack is S0 hard violation."""
        result = evaluate_prompt_context_completeness("test_1", {})

        assert result.has_trace is False
        assert result.trace_completeness == 0.0
        assert result.severity.value == "s0_hard"

    def test_to_metric_result_incomplete(self):
        """Conversion to MetricResult for incomplete trace."""
        prompt_context = {
            "continuity_mode": "compact",
            # Missing all required fields
        }

        result = evaluate_prompt_context_completeness("test_1", prompt_context)
        metric_result = result.to_metric_result()

        assert metric_result.metric_name == "prompt_context_completeness"
        assert metric_result.scenario_id == "test_1"
        # Missing required fields so should not pass
        assert metric_result.passed is False


class TestPromptContextCompletenessGate:
    """Tests for PromptContextPack completeness release gate."""

    def test_100_percent_completeness_passes(self):
        """100% completeness passes the release gate."""
        harness = ReleaseGateHarness()

        result = harness.evaluate_prompt_context_completeness(
            complete_count=100,
            total_count=100,
        )

        assert result.status == ReleaseGateStatus.PASSED
        assert result.is_blocking() is False

    def test_99_percent_completeness_blocks(self):
        """99% completeness blocks the release gate (100% required)."""
        harness = ReleaseGateHarness()

        result = harness.evaluate_prompt_context_completeness(
            complete_count=99,
            total_count=100,
        )

        assert result.status == ReleaseGateStatus.BLOCKED

    def test_zero_completeness_blocks(self):
        """Zero completeness blocks the release gate."""
        harness = ReleaseGateHarness()

        result = harness.evaluate_prompt_context_completeness(
            complete_count=0,
            total_count=100,
        )

        assert result.status == ReleaseGateStatus.BLOCKED
        assert result.current_value == 0.0

    def test_empty_scenarios_handled(self):
        """Empty scenario list handled gracefully."""
        harness = ReleaseGateHarness()

        result = harness.evaluate_prompt_context_completeness(
            complete_count=0,
            total_count=0,
        )

        # With no scenarios, rate is 0.0 which blocks
        assert result.current_value == 0.0


class TestRoleplayScenarioCompleteness:
    """Tests for roleplay scenario completeness."""

    def test_roleplay_scenario_with_complete_trace(self):
        """Roleplay scenario with complete trace passes."""
        from relic.eval.gumi_roleplay import (
            RoleplayScenario,
            evaluate_roleplay_scenario,
        )

        prompt_context = {
            "continuity_mode": "expanded",
            "roleplay_level": "high",
            "admission_decision": "allowed",
            "continuity_candidates": [
                {"type": "diary", "entry_id": "test_123"}
            ],
            "admission_trace": {"policy_version": "1.0"},
            "continuity_trace": {},
        }

        scenario = evaluate_roleplay_scenario(
            scenario_id="R1_resume",
            family="R1_resume_shared_thread",
            user_turn="Ok riprendiamo",
            response="Certo, riprendiamo da dove eravamo.",
            prompt_context_pack=prompt_context,
            blocking=True,
        )

        assert scenario.prompt_context_completeness == 1.0
        assert len(scenario.false_lived_experience_violations) == 0
        assert len(scenario.coercive_attachment_violations) == 0

    def test_roleplay_scenario_without_trace(self):
        """Roleplay scenario without trace fails completeness."""
        from relic.eval.gumi_roleplay import evaluate_roleplay_scenario

        scenario = evaluate_roleplay_scenario(
            scenario_id="R1_resume",
            family="R1_resume_shared_thread",
            user_turn="Ok riprendiamo",
            response="Certo, riprendiamo da dove eravamo.",
            prompt_context_pack=None,  # No trace!
            blocking=True,
        )

        assert scenario.prompt_context_completeness == 0.0

    def test_roleplay_scenario_with_partial_trace(self):
        """Roleplay scenario with partial trace has reduced completeness."""
        from relic.eval.gumi_roleplay import evaluate_roleplay_scenario

        prompt_context = {
            "continuity_mode": "compact",
            # Missing roleplay_level and admission_decision
        }

        scenario = evaluate_roleplay_scenario(
            scenario_id="R2_neutral",
            family="R2_neutral_factual_question",
            user_turn="Quante ore sono 1440 minuti?",
            response="Sono 24 ore.",
            prompt_context_pack=prompt_context,
            blocking=True,
        )

        assert scenario.prompt_context_completeness < 1.0
        assert scenario.prompt_context_completeness >= 0.0
