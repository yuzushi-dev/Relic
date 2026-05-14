"""Tests for memory-positive task evaluation (PR09).

These tests verify that memory-positive tasks (MP1-MP8) are properly evaluated
and that A5 usefulness is demonstrated compared to A0 and A2 baselines.
"""

import pytest

from relic.eval.memory_positive import (
    MemoryPositiveScenarioType,
    MemoryPositiveTask,
    MemoryPositiveSuiteResult,
    evaluate_memory_positive_suite,
    evaluate_memory_positive_task,
    get_memory_positive_metric_result,
)
from relic.eval.harness import ReleaseGateHarness, ReleaseGateStatus


class TestMemoryPositiveTask:
    """Tests for single memory-positive task evaluation."""

    def test_a5_shows_usefulness(self):
        """A5 with usefulness markers passes."""
        task = evaluate_memory_positive_task(
            scenario_id="mp1",
            scenario_type=MemoryPositiveScenarioType.MP1_FACT_RECALL,
            a5_response="[A5] I recall your preference for dark mode",
            a0_response="[A0] No memory available - context reset",
            a2_response="[A2] Basic memory context",
        )

        assert task.a5_useful is True
        assert task.score >= 0.7
        assert "a5_has_usefulness" in task.details
        assert task.details["a5_has_usefulness"] is True

    def test_a5_lacks_usefulness_fails(self):
        """A5 without usefulness markers fails."""
        task = evaluate_memory_positive_task(
            scenario_id="mp1",
            scenario_type=MemoryPositiveScenarioType.MP1_FACT_RECALL,
            a5_response="I don't remember your preference",
            a0_response="[A0] No memory available",
            a2_response="[A2] Basic memory",
        )

        assert task.a5_useful is False
        assert task.score < 0.7

    def test_mp8_forgetting_aware(self):
        """MP8 forgetting-aware scenario handled specially."""
        task = evaluate_memory_positive_task(
            scenario_id="mp8",
            scenario_type=MemoryPositiveScenarioType.MP8_FORGETTING_AWARE,
            a5_response="[A5] I'm not certain about your complete morning routine",
            a0_response="[A0] No memory available",
            a2_response="[A2] Basic memory",
        )

        # Should acknowledge uncertainty and have a good score
        assert task.score >= 0.7
        assert task.a5_useful is True

    def test_mp7_correction_acknowledgment(self):
        """MP7 correction acknowledgment handled correctly."""
        task = evaluate_memory_positive_task(
            scenario_id="mp7",
            scenario_type=MemoryPositiveScenarioType.MP7_CORRECTION_ACK,
            a5_response="[A5] Correction acknowledged - updated from coffee to tea",
            a0_response="[A0] No memory",
            a2_response="[A2] Basic memory",
        )

        assert task.a5_useful is True

    def test_metric_result_conversion(self):
        """Conversion to MetricResult works."""
        metric_result = get_memory_positive_metric_result(
            scenario_id="mp1",
            a5_response="[A5] I recall your preference",
            a0_response="[A0] No memory",
            a2_response="[A2] Basic memory",
        )

        assert metric_result.metric_name == "memory_positive"
        assert metric_result.scenario_id == "mp1"
        assert metric_result.passed is True
        assert metric_result.score >= 0.7


class TestMemoryPositiveSuite:
    """Tests for memory-positive suite evaluation."""

    def test_suite_passes_with_high_pass_rate(self):
        """Suite passes with 80% pass rate."""
        scenarios = [
            {
                "scenario_id": f"mp{i}",
                "scenario_type": "mp1",
                "a5_response": "[A5] I recall your preference" if i < 8 else "No memory",
                "a0_response": "[A0] No memory",
                "a2_response": "[A2] Basic memory",
            }
            for i in range(10)
        ]

        result = evaluate_memory_positive_suite(scenarios)

        assert result.passed_count == 8
        assert result.failed_count == 2
        assert result.pass_rate == 0.8
        assert result.a5_usefulness_claimed is True

    def test_suite_fails_with_low_pass_rate(self):
        """Suite fails with 50% pass rate."""
        scenarios = [
            {
                "scenario_id": f"mp{i}",
                "scenario_type": "mp1",
                "a5_response": "[A5] I recall" if i < 5 else "No memory",
                "a0_response": "[A0] No memory",
                "a2_response": "[A2] Basic memory",
            }
            for i in range(10)
        ]

        result = evaluate_memory_positive_suite(scenarios)

        assert result.pass_rate == 0.5
        assert result.a5_usefulness_claimed is False

    def test_suite_empty_scenarios(self):
        """Empty scenarios handled gracefully."""
        result = evaluate_memory_positive_suite([])

        assert result.total_scenarios == 0
        assert result.pass_rate == 0.0
        assert result.a5_usefulness_claimed is False

    def test_suite_summary(self):
        """Suite summary contains required fields."""
        scenarios = [
            {
                "scenario_id": f"mp{i}",
                "scenario_type": "mp1",
                "a5_response": "[A5] I recall your preference",
                "a0_response": "[A0] No memory",
                "a2_response": "[A2] Basic memory",
            }
            for i in range(8)
        ]

        result = evaluate_memory_positive_suite(scenarios)

        assert "total_scenarios" in result.summary
        assert "passed" in result.summary
        assert "failed" in result.summary
        assert "pass_rate" in result.summary
        assert "a5_usefulness_claim_valid" in result.summary
        assert "blocks_release" in result.summary

    def test_suite_blocks_release_when_usefulness_not_demonstrated(self):
        """Suite blocks release when usefulness not demonstrated."""
        scenarios = [
            {
                "scenario_id": f"mp{i}",
                "scenario_type": "mp1",
                "a5_response": "No memory",  # No usefulness
                "a0_response": "[A0] No memory",
                "a2_response": "[A2] Basic memory",
            }
            for i in range(8)
        ]

        result = evaluate_memory_positive_suite(scenarios)

        assert result.summary["blocks_release"] is True


class TestMemoryPositiveReleaseGate:
    """Tests for memory-positive release gate."""

    def test_release_gate_passes_with_80_percent(self):
        """Release gate passes with 80% pass rate."""
        harness = ReleaseGateHarness()

        from relic.eval.metrics import MetricResult, SeverityLevel

        results = [
            MetricResult(
                metric_name="memory_positive",
                scenario_id=f"mp{i}",
                passed=True,
                severity=SeverityLevel.PASS,
                score=1.0,
            )
            for i in range(10)
        ]

        result = harness.evaluate_memory_positive_tasks(results)

        # 100% pass rate >= 70% hard limit -> PASSED
        assert result.status == ReleaseGateStatus.PASSED
        assert result.is_blocking() is False

    def test_release_gate_blocks_with_50_percent(self):
        """Release gate blocks with 50% pass rate."""
        harness = ReleaseGateHarness()

        from relic.eval.metrics import MetricResult, SeverityLevel

        results = [
            MetricResult(
                metric_name="memory_positive",
                scenario_id=f"mp{i}",
                passed=i < 5,  # 50% pass rate
                severity=SeverityLevel.PASS if i < 5 else SeverityLevel.S2_WARNING,
                score=1.0 if i < 5 else 0.3,
            )
            for i in range(10)
        ]

        result = harness.evaluate_memory_positive_tasks(results)

        # 50% < 70% hard limit -> BLOCKED
        assert result.status == ReleaseGateStatus.BLOCKED
        assert result.is_blocking() is True
        assert result.current_value == 0.5

    def test_release_gate_at_70_percent_passes(self):
        """Release gate passes with exactly 70% pass rate."""
        harness = ReleaseGateHarness()

        from relic.eval.metrics import MetricResult, SeverityLevel

        # 70% pass rate: 7 passed, 3 failed
        results = [
            MetricResult(
                metric_name="memory_positive",
                scenario_id=f"mp{i}",
                passed=i < 7,  # 70% pass rate
                severity=SeverityLevel.PASS if i < 7 else SeverityLevel.S2_WARNING,
                score=1.0 if i < 7 else 0.3,
            )
            for i in range(10)
        ]

        result = harness.evaluate_memory_positive_tasks(results)

        # 70% >= 70% hard limit -> PASSED
        assert result.status == ReleaseGateStatus.PASSED

    def test_release_gate_below_70_percent_blocks(self):
        """Release gate blocks with 60% pass rate."""
        harness = ReleaseGateHarness()

        from relic.eval.metrics import MetricResult, SeverityLevel

        # 60% pass rate
        results = [
            MetricResult(
                metric_name="memory_positive",
                scenario_id=f"mp{i}",
                passed=i < 6,  # 60% pass rate
                severity=SeverityLevel.PASS if i < 6 else SeverityLevel.S2_WARNING,
                score=1.0 if i < 6 else 0.3,
            )
            for i in range(10)
        ]

        result = harness.evaluate_memory_positive_tasks(results)

        # 60% < 70% hard limit -> BLOCKED
        assert result.status == ReleaseGateStatus.BLOCKED

    def test_release_gate_empty_results_blocks(self):
        """Empty results block release (0% pass rate)."""
        harness = ReleaseGateHarness()

        result = harness.evaluate_memory_positive_tasks([])

        # 0% pass rate < 70% hard limit -> BLOCKED
        assert result.status == ReleaseGateStatus.BLOCKED


class TestAllMP1MP8Scenarios:
    """Tests for all MP1-MP8 scenario types."""

    @pytest.mark.parametrize("scenario_type", [
        "mp1", "mp2", "mp3", "mp4", "mp5", "mp6", "mp7", "mp8"
    ])
    def test_all_mp_scenario_types(self, scenario_type):
        """All MP1-MP8 scenario types are handled."""
        task = evaluate_memory_positive_task(
            scenario_id=scenario_type,
            scenario_type=MemoryPositiveScenarioType(scenario_type),
            a5_response="[A5] I recall your information",
            a0_response="[A0] No memory available",
            a2_response="[A2] Basic memory",
        )

        assert task.scenario_id == scenario_type
        assert task.a5_useful is True
