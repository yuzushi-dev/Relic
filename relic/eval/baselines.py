"""Baseline evaluation implementations for Relic E2E.

This module implements A0-A5 baseline configurations for evaluation.
Each baseline represents a different level of memory and correction capability.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from relic.eval.fixtures import EvalScenario, FixtureType, ScenarioType
from relic.eval.mock_model import MockModel, create_mock_model


class BaselineType(Enum):
    """Baseline configuration types."""

    A0 = "a0"  # No memory, no correction
    A1 = "a1"  # No memory capability
    A2 = "a2"  # Basic memory without correction
    A3 = "a3"  # Correction only
    A4 = "a4"  # Partial memory+correction
    A5 = "a5"  # Full memory+correction


@dataclass
class Baseline:
    """Represents a baseline evaluation configuration."""

    name: str
    baseline_type: BaselineType
    description: str
    memory_enabled: bool
    correction_enabled: bool
    mock_model: MockModel

    def evaluate(self, scenario: EvalScenario) -> dict[str, Any]:
        """Evaluate a single scenario with this baseline."""
        response = self.mock_model.generate(scenario.prompt)

        return {
            "baseline": self.name,
            "scenario_id": scenario.scenario_id,
            "scenario_type": scenario.scenario_type.value,
            "response": response.content,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
            "memory_enabled": self.memory_enabled,
            "correction_enabled": self.correction_enabled,
        }

    def evaluate_batch(self, scenarios: list[EvalScenario]) -> list[dict[str, Any]]:
        """Evaluate multiple scenarios with this baseline."""
        return [self.evaluate(s) for s in scenarios]


@dataclass
class BaselineMetrics:
    """Metrics from baseline evaluation."""

    baseline: str
    total_scenarios: int
    successful_evaluations: int
    average_tokens: float
    average_latency_ms: float
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "total_scenarios": self.total_scenarios,
            "successful_evaluations": self.successful_evaluations,
            "average_tokens": self.average_tokens,
            "average_latency_ms": self.average_latency_ms,
            "results": self.results,
        }


def create_baseline(baseline_type: BaselineType) -> Baseline:
    """Factory function to create a baseline."""
    configs = {
        BaselineType.A0: {
            "description": "No memory, no correction - stateless baseline",
            "memory_enabled": False,
            "correction_enabled": False,
        },
        BaselineType.A1: {
            "description": "No memory capability",
            "memory_enabled": False,
            "correction_enabled": False,
        },
        BaselineType.A2: {
            "description": "Basic memory without correction",
            "memory_enabled": True,
            "correction_enabled": False,
        },
        BaselineType.A3: {
            "description": "Correction only",
            "memory_enabled": False,
            "correction_enabled": True,
        },
        BaselineType.A4: {
            "description": "Partial memory+correction",
            "memory_enabled": True,
            "correction_enabled": True,
        },
        BaselineType.A5: {
            "description": "Full memory+correction - target system",
            "memory_enabled": True,
            "correction_enabled": True,
        },
    }

    config = configs[baseline_type]
    mock_model = create_mock_model(baseline_type.value)

    return Baseline(
        name=baseline_type.value,
        baseline_type=baseline_type,
        description=config["description"],
        memory_enabled=config["memory_enabled"],
        correction_enabled=config["correction_enabled"],
        mock_model=mock_model,
    )


def run_baseline(
    baseline: Baseline,
    scenarios: list[EvalScenario],
) -> BaselineMetrics:
    """Run evaluation for a single baseline."""
    results = baseline.evaluate_batch(scenarios)

    total_tokens = sum(r["tokens_used"] for r in results)
    total_latency = sum(r["latency_ms"] for r in results)

    return BaselineMetrics(
        baseline=baseline.name,
        total_scenarios=len(scenarios),
        successful_evaluations=len(results),
        average_tokens=total_tokens / len(scenarios) if scenarios else 0,
        average_latency_ms=total_latency / len(scenarios) if scenarios else 0,
        results=results,
    )


def run_baselines(scenarios: list[EvalScenario] | None = None) -> dict[str, BaselineMetrics]:
    """Run evaluation across all baselines (A0-A5).

    If no scenarios provided, uses default evaluation scenarios.
    Returns a dictionary mapping baseline name to metrics.
    """
    if scenarios is None:
        scenarios = _get_default_scenarios()

    all_metrics: dict[str, BaselineMetrics] = {}

    for baseline_type in BaselineType:
        baseline = create_baseline(baseline_type)
        metrics = run_baseline(baseline, scenarios)
        all_metrics[baseline.name] = metrics

    return all_metrics


def _get_default_scenarios() -> list[EvalScenario]:
    """Get default evaluation scenarios."""
    return [
        EvalScenario(
            scenario_id="default_mp1",
            scenario_type=ScenarioType.MP1,
            fixture_type=FixtureType.MEMORY_POSITIVE,
            prompt="User asks about previous conversation topic",
            expected_response="Recall from memory",
        ),
        EvalScenario(
            scenario_id="default_mp2",
            scenario_type=ScenarioType.MP2,
            fixture_type=FixtureType.MEMORY_POSITIVE,
            prompt="User asks me to remember their preference",
            expected_response="Acknowledge preference",
        ),
        EvalScenario(
            scenario_id="default_s0",
            scenario_type=ScenarioType.S0_HARD,
            fixture_type=FixtureType.PRIVACY,
            prompt="Test S0 hard violation scenario",
            expected_response="Block response",
        ),
        EvalScenario(
            scenario_id="default_s1",
            scenario_type=ScenarioType.S1_QUARANTINE,
            fixture_type=FixtureType.PRIVACY,
            prompt="Test S1 quarantine scenario",
            expected_response="Quarantine response",
        ),
        EvalScenario(
            scenario_id="default_s2",
            scenario_type=ScenarioType.S2_WARNING,
            fixture_type=FixtureType.PRIVACY,
            prompt="Test S2 warning scenario",
            expected_response="Warning response",
        ),
    ]


def compare_baselines(
    all_metrics: dict[str, BaselineMetrics],
) -> dict[str, Any]:
    """Compare metrics across baselines.

    Returns comparison metrics showing how A5 compares to other baselines.
    """
    comparison = {
        "baseline_comparison": {},
        "memory_effect": {},
        "correction_effect": {},
    }

    if "a0" in all_metrics and "a5" in all_metrics:
        comparison["baseline_comparison"]["a5_vs_a0"] = {
            "token_delta": all_metrics["a5"].average_tokens - all_metrics["a0"].average_tokens,
            "latency_delta": all_metrics["a5"].average_latency_ms
            - all_metrics["a0"].average_latency_ms,
        }

    if "a2" in all_metrics and "a5" in all_metrics:
        comparison["memory_effect"]["a5_vs_a2"] = {
            "token_delta": all_metrics["a5"].average_tokens - all_metrics["a2"].average_tokens,
            "latency_delta": all_metrics["a5"].average_latency_ms
            - all_metrics["a2"].average_latency_ms,
        }

    if "a3" in all_metrics and "a5" in all_metrics:
        comparison["correction_effect"]["a5_vs_a3"] = {
            "token_delta": all_metrics["a5"].average_tokens - all_metrics["a3"].average_tokens,
            "latency_delta": all_metrics["a5"].average_latency_ms
            - all_metrics["a3"].average_latency_ms,
        }

    return comparison
