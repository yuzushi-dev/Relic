"""Evaluation report generation for Relic E2E.

This module generates evaluation reports with metrics summaries,
severity breakdowns, and comparison tables.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class EvalReport:
    """Evaluation report container."""

    timestamp: str
    baseline: str | None
    total_scenarios: int
    passed: int
    failed: int
    severity_summary: dict[str, Any]
    metric_details: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    comparisons: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "baseline": self.baseline,
            "total_scenarios": self.total_scenarios,
            "passed": self.passed,
            "failed": self.failed,
            "severity_summary": self.severity_summary,
            "metric_details": self.metric_details,
            "comparisons": self.comparisons,
            "metadata": self.metadata,
        }

    def to_json(self, output_path: Path | str | None = None) -> str:
        """Export report as JSON."""
        json_str = json.dumps(self.to_dict(), indent=2)
        if output_path:
            Path(output_path).write_text(json_str)
        return json_str

    def to_markdown(self, output_path: Path | str | None = None) -> str:
        """Export report as Markdown."""
        md = self._generate_markdown()
        if output_path:
            Path(output_path).write_text(md)
        return md

    def _generate_markdown(self) -> str:
        """Generate Markdown representation of the report."""
        lines = [
            "# Relic E2E Evaluation Report",
            "",
            f"**Generated:** {self.timestamp}",
            f"**Baseline:** {self.baseline or 'All baselines'}",
            "",
            "## Summary",
            "",
            f"- Total Scenarios: {self.total_scenarios}",
            f"- Passed: {self.passed}",
            f"- Failed: {self.failed}",
            f"- Pass Rate: {self.passed / self.total_scenarios * 100 if self.total_scenarios else 0:.1f}%",
            "",
            "## Severity Breakdown",
            "",
        ]

        # Add severity breakdown
        s0 = self.severity_summary.get("s0_hard_violations", {})
        s1 = self.severity_summary.get("s1_quarantine", {})
        s2 = self.severity_summary.get("s2_warnings", {})
        passed = self.severity_summary.get("passed", {})

        lines.extend(
            [
                "| Severity | Count | Percentage |",
                "|---------|-------|------------|",
                f"| S0 Hard Violation | {s0.get('count', 0)} | {s0.get('percentage', 0) * 100:.1f}% |",
                f"| S1 Quarantine | {s1.get('count', 0)} | {s1.get('percentage', 0) * 100:.1f}% |",
                f"| S2 Warning | {s2.get('count', 0)} | {s2.get('percentage', 0) * 100:.1f}% |",
                f"| Pass | {passed.get('count', 0)} | {passed.get('percentage', 0) * 100:.1f}% |",
                "",
            ]
        )

        # Add comparison table if available
        if self.comparisons:
            lines.extend(
                [
                    "## Baseline Comparison",
                    "",
                    "| Baseline A | Baseline B | Token Delta | Latency Delta |",
                    "|------------|------------|-------------|---------------|",
                ]
            )
            for comparison_key, comp_data in self.comparisons.items():
                for sub_key, sub_data in comp_data.items():
                    if isinstance(sub_data, dict):
                        lines.append(
                            f"| {comparison_key.replace('_', ' ').title()} | "
                            f"{sub_key.replace('_', ' ').title()} | "
                            f"{sub_data.get('token_delta', 0):.1f} | "
                            f"{sub_data.get('latency_delta', 0):.1f}ms |"
                        )
            lines.append("")

        # Add metric details
        if self.metric_details:
            lines.extend(
                [
                    "## Metric Details",
                    "",
                ]
            )
            for metric_name, results in self.metric_details.items():
                lines.extend(
                    [
                        f"### {metric_name.replace('_', ' ').title()}",
                        "",
                        f"Evaluations: {len(results)}",
                        "",
                    ]
                )

        return "\n".join(lines)


def generate_report(
    baseline_metrics: dict[str, Any] | None = None,
    severity_metrics: dict[str, Any] | None = None,
    comparisons: dict[str, Any] | None = None,
    baseline: str | None = None,
) -> EvalReport:
    """Generate an evaluation report from metrics.

    Args:
        baseline_metrics: Metrics from baseline evaluation
        severity_metrics: Aggregated severity metrics
        comparisons: Baseline comparison data
        baseline: Specific baseline name if single baseline

    Returns:
        EvalReport instance
    """
    now = datetime.utcnow().isoformat() + "Z"

    total_scenarios = 0
    passed = 0
    failed = 0

    # Extract counts from severity metrics
    severity_summary = {
        "s0_hard_violations": {"count": 0, "percentage": 0},
        "s1_quarantine": {"count": 0, "percentage": 0},
        "s2_warnings": {"count": 0, "percentage": 0},
        "passed": {"count": 0, "percentage": 0},
    }

    if severity_metrics:
        summary = severity_metrics.get("summary", {})
        total_scenarios = summary.get("total_evaluations", 0)

        for key in ["s0_hard_violations", "s1_quarantine", "s2_warnings", "passed"]:
            severity_summary[key] = summary.get(key, {"count": 0, "percentage": 0})

        passed = severity_summary["passed"]["count"]
        failed = total_scenarios - passed

    metric_details = {}
    if baseline_metrics:
        # Convert baseline metrics to detail format
        if isinstance(baseline_metrics, dict):
            for baseline_name, metrics in baseline_metrics.items():
                if isinstance(metrics, dict) and "results" in metrics:
                    metric_details[baseline_name] = metrics["results"]

    return EvalReport(
        timestamp=now,
        baseline=baseline,
        total_scenarios=total_scenarios,
        passed=passed,
        failed=failed,
        severity_summary=severity_summary,
        metric_details=metric_details,
        comparisons=comparisons or {},
    )


def save_report(
    report: EvalReport,
    output_dir: Path | str,
    formats: list[str] | None = None,
) -> dict[str, Path]:
    """Save report in multiple formats.

    Args:
        report: EvalReport to save
        output_dir: Output directory
        formats: List of formats ("json", "markdown", or both)

    Returns:
        Dictionary mapping format to output path
    """
    if formats is None:
        formats = ["json", "markdown"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = {}
    timestamp = report.timestamp.replace(":", "-").replace(".", "-")

    if "json" in formats:
        json_path = output_dir / f"report_{timestamp}.json"
        report.to_json(json_path)
        outputs["json"] = json_path

    if "markdown" in formats:
        md_path = output_dir / f"report_{timestamp}.md"
        report.to_markdown(md_path)
        outputs["markdown"] = md_path

    return outputs
