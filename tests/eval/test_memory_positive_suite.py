"""Tests for memory-positive suite (MP1-MP8).

This test module validates that A5 demonstrates usefulness compared to
A0 (no memory) and A2 (basic memory) baselines across memory-positive scenarios.
"""

import pytest

from relic.eval.baselines import BaselineType, create_baseline
from relic.eval.fixtures import EvalScenario, FixtureType, ScenarioType
from relic.eval.metrics import (
    MemoryPositiveMetric,
    SeverityLevel,
)


class TestMemoryPositiveSuite:
    """Tests for MP1-MP8 memory-positive scenarios."""

    @pytest.fixture
    def memory_positive_scenarios(self):
        """Fixture providing MP1-MP8 scenarios."""
        return [
            EvalScenario(
                scenario_id="mp1",
                scenario_type=ScenarioType.MP1,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="Remember: I prefer dark mode",
                expected_response="Acknowledged preference",
            ),
            EvalScenario(
                scenario_id="mp2",
                scenario_type=ScenarioType.MP2,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="Remember my name is Alice",
                expected_response="Name acknowledged",
            ),
            EvalScenario(
                scenario_id="mp3",
                scenario_type=ScenarioType.MP3,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="I like coffee with oat milk",
                expected_response="Preference recorded",
            ),
            EvalScenario(
                scenario_id="mp4",
                scenario_type=ScenarioType.MP4,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="My favorite color is blue",
                expected_response="Color preference stored",
            ),
            EvalScenario(
                scenario_id="mp5",
                scenario_type=ScenarioType.MP5,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="We discussed the Q3 report last week",
                expected_response="Recall Q3 discussion",
            ),
            EvalScenario(
                scenario_id="mp6",
                scenario_type=ScenarioType.MP6,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="Update: I moved to New York",
                expected_response="Location updated",
            ),
            EvalScenario(
                scenario_id="mp7",
                scenario_type=ScenarioType.MP7,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="Actually, I prefer tea instead of coffee",
                expected_response="Correction acknowledged",
            ),
            EvalScenario(
                scenario_id="mp8",
                scenario_type=ScenarioType.MP8,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="Do you remember my morning routine?",
                expected_response="Recall routine or acknowledge uncertainty",
            ),
        ]

    def test_all_mp_scenarios_present(self, memory_positive_scenarios):
        """Test all MP1-MP8 scenarios are present."""
        scenario_ids = {s.scenario_id for s in memory_positive_scenarios}
        expected = {"mp1", "mp2", "mp3", "mp4", "mp5", "mp6", "mp7", "mp8"}
        assert scenario_ids == expected

    def test_a5_vs_a0_memory_advantage(self):
        """Test A5 shows memory advantage over A0 (no memory)."""
        metric = MemoryPositiveMetric()

        result = metric.evaluate(
            scenario_id="mp1",
            a5_response="[A5] I recall your preference for dark mode",
            a0_response="[A0] No memory available - context reset",
            a2_response="[A2] Basic memory context",
        )

        assert result.passed is True
        assert result.score == 1.0
        assert result.severity == SeverityLevel.PASS

    def test_a5_vs_a2_memory_advantage(self):
        """Test A5 shows improvement over A2 (basic memory)."""
        metric = MemoryPositiveMetric()

        result = metric.evaluate(
            scenario_id="mp1",
            a5_response="[A5] Your dark mode preference has been updated",
            a0_response="[A0] No memory available",
            a2_response="[A2] I recall dark mode preference",
        )

        # A5 should still show advantage even when A2 has some memory
        assert result.severity == SeverityLevel.PASS

    def test_mp1_fact_recall(self):
        """Test MP1: Fact recall after context switch."""
        metric = MemoryPositiveMetric()

        result = metric.evaluate(
            scenario_id="mp1",
            a5_response="[A5] I recall you prefer dark mode",
            a0_response="[A0] No memory",
            a2_response="[A2] Basic recall",
        )

        assert result.passed is True
        assert "a5_memory_advantage" in result.details

    def test_mp2_preference_recall(self):
        """Test MP2: Preference recall after interruption."""
        metric = MemoryPositiveMetric()

        result = metric.evaluate(
            scenario_id="mp2",
            a5_response="[A5] Your name is Alice",
            a0_response="[A0] No memory",
            a2_response="[A2] Basic memory",
        )

        assert result.passed is True

    def test_mp7_correction_acknowledgment(self):
        """Test MP7: Memory correction acknowledgment."""
        metric = MemoryPositiveMetric()

        result = metric.evaluate(
            scenario_id="mp7",
            a5_response="[A5] Correction acknowledged - preference updated from coffee to tea",
            a0_response="[A0] No memory",
            a2_response="[A2] Basic memory",
        )

        assert result.passed is True
        assert result.score >= 0.7

    def test_mp8_forgetting_aware(self):
        """Test MP8: Forgetting-aware response when memory uncertain."""
        metric = MemoryPositiveMetric()

        # When A5 is uncertain, it should acknowledge rather than guess
        result = metric.evaluate(
            scenario_id="mp8",
            a5_response="[A5] I'm not certain about your complete morning routine",
            a0_response="[A0] No memory",
            a2_response="[A2] Basic memory",
        )

        # Even uncertain A5 should be distinguishable from no memory
        assert result.severity in [SeverityLevel.PASS, SeverityLevel.S2_WARNING]

    def test_full_suite_comparison(self, memory_positive_scenarios):
        """Test running full MP1-MP8 suite across baselines."""
        # Evaluate all scenarios with A5 and baselines
        a5_baseline = create_baseline(BaselineType.A5)
        a0_baseline = create_baseline(BaselineType.A0)
        a2_baseline = create_baseline(BaselineType.A2)

        metric = MemoryPositiveMetric()
        results = []

        for scenario in memory_positive_scenarios:
            a5_result = a5_baseline.evaluate(scenario)
            a0_result = a0_baseline.evaluate(scenario)
            a2_result = a2_baseline.evaluate(scenario)

            mp_result = metric.evaluate(
                scenario_id=scenario.scenario_id,
                a5_response=a5_result["response"],
                a0_response=a0_result["response"],
                a2_response=a2_result["response"],
            )
            results.append(mp_result)

        # All MP scenarios should pass or have acceptable scores
        passed_count = sum(1 for r in results if r.passed)
        average_score = sum(r.score for r in results) / len(results)

        assert passed_count >= 6  # At least 75% pass rate
        assert average_score >= 0.6  # Average score above 0.6

    def test_a5_usefulness_not_claimed_without_results(self):
        """Verify A5 usefulness requires actual MP suite results.

        This test ensures we don't make A5 usefulness claims
        without running the memory-positive task results.
        """
        # This test validates the design constraint
        # If no results exist, we should not claim A5 is useful
        metric = MemoryPositiveMetric()

        # Without comparison data, we can't claim usefulness
        result = metric.evaluate(
            scenario_id="mp1",
            a5_response="[A5] I have full memory",
            a0_response="",  # Empty - no comparison
            a2_response="",  # Empty - no comparison
        )

        # Should fail or warn without baseline comparison
        assert result.score <= 0.7 or result.severity != SeverityLevel.PASS
