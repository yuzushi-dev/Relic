"""Tests for baselines module."""


from relic.eval.baselines import (
    BaselineMetrics,
    BaselineType,
    compare_baselines,
    create_baseline,
    run_baseline,
    run_baselines,
)
from relic.eval.fixtures import EvalScenario, FixtureType, ScenarioType


class TestBaseline:
    """Tests for Baseline class."""

    def test_create_baseline_a0(self):
        """Test creating A0 baseline."""
        baseline = create_baseline(BaselineType.A0)

        assert baseline.name == "a0"
        assert baseline.baseline_type == BaselineType.A0
        assert baseline.memory_enabled is False
        assert baseline.correction_enabled is False

    def test_create_baseline_a5(self):
        """Test creating A5 baseline."""
        baseline = create_baseline(BaselineType.A5)

        assert baseline.name == "a5"
        assert baseline.baseline_type == BaselineType.A5
        assert baseline.memory_enabled is True
        assert baseline.correction_enabled is True

    def test_baseline_evaluate(self):
        """Test baseline evaluation of a scenario."""
        baseline = create_baseline(BaselineType.A5)

        scenario = EvalScenario(
            scenario_id="test_1",
            scenario_type=ScenarioType.MP1,
            fixture_type=FixtureType.MEMORY_POSITIVE,
            prompt="Test prompt",
            expected_response="Test response",
        )

        result = baseline.evaluate(scenario)

        assert result["baseline"] == "a5"
        assert result["scenario_id"] == "test_1"
        assert "response" in result
        assert "tokens_used" in result

    def test_baseline_evaluate_batch(self):
        """Test batch evaluation."""
        baseline = create_baseline(BaselineType.A0)

        scenarios = [
            EvalScenario(
                scenario_id=f"test_{i}",
                scenario_type=ScenarioType.MP1,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt=f"Prompt {i}",
                expected_response=f"Response {i}",
            )
            for i in range(3)
        ]

        results = baseline.evaluate_batch(scenarios)

        assert len(results) == 3
        assert all(r["baseline"] == "a0" for r in results)


class TestRunBaseline:
    """Tests for run_baseline function."""

    def test_run_baseline_empty_scenarios(self):
        """Test run_baseline with empty scenario list."""
        baseline = create_baseline(BaselineType.A0)
        metrics = run_baseline(baseline, [])

        assert metrics.baseline == "a0"
        assert metrics.total_scenarios == 0

    def test_run_baseline_with_scenarios(self):
        """Test run_baseline with scenarios."""
        baseline = create_baseline(BaselineType.A5)

        scenarios = [
            EvalScenario(
                scenario_id="test_1",
                scenario_type=ScenarioType.MP1,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="Remember this",
                expected_response="Acknowledged",
            ),
        ]

        metrics = run_baseline(baseline, scenarios)

        assert metrics.baseline == "a5"
        assert metrics.total_scenarios == 1
        assert metrics.successful_evaluations == 1
        assert len(metrics.results) == 1


class TestRunBaselines:
    """Tests for run_baselines function."""

    def test_run_all_baselines(self):
        """Test running all baselines (A0-A5)."""
        baselines = run_baselines()

        assert len(baselines) == 6
        assert "a0" in baselines
        assert "a5" in baselines

    def test_run_baselines_with_custom_scenarios(self):
        """Test running baselines with custom scenarios."""
        scenarios = [
            EvalScenario(
                scenario_id="custom_1",
                scenario_type=ScenarioType.MP1,
                fixture_type=FixtureType.MEMORY_POSITIVE,
                prompt="Test",
                expected_response="Result",
            ),
        ]

        baselines = run_baselines(scenarios=scenarios)

        assert len(baselines) == 6
        for name, metrics in baselines.items():
            assert metrics.total_scenarios == 1


class TestCompareBaselines:
    """Tests for compare_baselines function."""

    def test_compare_with_all_baselines(self):
        """Test comparison with all baselines available."""
        baselines = run_baselines()
        comparison = compare_baselines(baselines)

        assert "baseline_comparison" in comparison
        assert "memory_effect" in comparison
        assert "correction_effect" in comparison

    def test_compare_partial_baselines(self):
        """Test comparison with only some baselines."""

        partial = {
            "a0": BaselineMetrics(
                baseline="a0",
                total_scenarios=5,
                successful_evaluations=5,
                average_tokens=100,
                average_latency_ms=50,
            ),
            "a5": BaselineMetrics(
                baseline="a5",
                total_scenarios=5,
                successful_evaluations=5,
                average_tokens=150,
                average_latency_ms=75,
            ),
        }

        comparison = compare_baselines(partial)

        assert "baseline_comparison" in comparison
        assert "a5_vs_a0" in comparison["baseline_comparison"]
