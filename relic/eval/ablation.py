"""Ablation study module for Relic E2E.

This module enables ablation studies to measure the contribution
of individual components (memory, correction, privacy gates) to overall performance.
"""

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AblationResult:
    """Result of an ablation experiment."""

    experiment_name: str
    baseline_score: float
    ablated_score: float
    component_removed: str
    delta: float
    percentage_change: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_name": self.experiment_name,
            "baseline_score": self.baseline_score,
            "ablated_score": self.ablated_score,
            "component_removed": self.component_removed,
            "delta": self.delta,
            "percentage_change": self.percentage_change,
            "metadata": self.metadata,
        }


@dataclass
class AblationComparison:
    """Comparison table for ablation studies."""

    baseline: str
    components: list[str]
    results: list[AblationResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "components": self.components,
            "results": [r.to_dict() for r in self.results],
        }

    def to_markdown_table(self) -> str:
        """Generate Markdown table for ablation comparison."""
        lines = [
            "| Component Removed | Baseline Score | Ablated Score | Delta | % Change |",
            "|-------------------|---------------|---------------|-------|----------|",
        ]

        for result in self.results:
            lines.append(
                f"| {result.component_removed} | "
                f"{result.baseline_score:.4f} | "
                f"{result.ablated_score:.4f} | "
                f"{result.delta:+.4f} | "
                f"{result.percentage_change:+.2f}% |"
            )

        return "\n".join(lines)


class AblationStudy:
    """Ablation study executor for component analysis."""

    COMPONENTS = [
        "memory",
        "correction",
        "privacy_gate",
        "consent_manager",
        "incident_reporter",
    ]

    def __init__(self, baseline_metrics: dict[str, Any] | None = None):
        self.baseline_metrics = baseline_metrics or {}
        self._results: list[AblationResult] = []

    def run_ablations(
        self,
        baseline_score: float,
        component_scores: dict[str, float],
        experiment_name: str = "default",
    ) -> list[AblationResult]:
        """Run ablation studies for all components.

        Args:
            baseline_score: Score with all components enabled (A5)
            component_scores: Dict mapping component name to score without it
            experiment_name: Name for this experiment

        Returns:
            List of AblationResult for each component
        """
        results = []

        for component in self.COMPONENTS:
            if component in component_scores:
                ablated_score = component_scores[component]
            else:
                # Component not measured - use baseline as placeholder
                ablated_score = baseline_score

            delta = ablated_score - baseline_score
            percentage_change = (delta / baseline_score * 100) if baseline_score != 0 else 0

            result = AblationResult(
                experiment_name=experiment_name,
                baseline_score=baseline_score,
                ablated_score=ablated_score,
                component_removed=component,
                delta=delta,
                percentage_change=percentage_change,
                metadata={"component": component},
            )
            results.append(result)

        self._results.extend(results)
        return results

    def get_comparison_table(self, baseline: str = "a5") -> AblationComparison:
        """Get ablation comparison table."""
        return AblationComparison(
            baseline=baseline,
            components=self.COMPONENTS,
            results=self._results,
        )

    def export_comparison(self, output_path: str | None = None) -> str:
        """Export ablation comparison as JSON or Markdown."""
        comparison = self.get_comparison_table()

        if output_path and output_path.endswith(".json"):
            with open(output_path, "w") as f:
                json.dump(comparison.to_dict(), f, indent=2)
            return f"Ablation comparison saved to {output_path}"

        return comparison.to_markdown_table()


def compute_ablation_comparison(
    a5_metrics: dict[str, float],
    component_metrics: dict[str, dict[str, float]],
) -> dict[str, AblationResult]:
    """Compute ablation comparison between A5 and component-ablated baselines.

    Args:
        a5_metrics: Metrics from full A5 configuration
        component_metrics: Metrics from configurations with individual components disabled

    Returns:
        Dict mapping component name to AblationResult
    """
    results = {}

    for component, metrics in component_metrics.items():
        # Compute composite score (average of key metrics)
        a5_score = (
            sum(a5_metrics.get(k, 0) for k in ["memory_positive", "correction_obedience"]) / 2
        )
        component_score = (
            sum(metrics.get(k, 0) for k in ["memory_positive", "correction_obedience"]) / 2
        )

        delta = component_score - a5_score
        percentage_change = (delta / a5_score * 100) if a5_score != 0 else 0

        results[component] = AblationResult(
            experiment_name=f"ablation_{component}",
            baseline_score=a5_score,
            ablated_score=component_score,
            component_removed=component,
            delta=delta,
            percentage_change=percentage_change,
            metadata={"component": component, "metrics": metrics},
        )

    return results
