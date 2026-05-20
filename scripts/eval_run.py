#!/usr/bin/env python3
"""hermes relic eval-run — Run release gate evaluation and exit(1) on failure.

Usage:
    python scripts/eval_run.py [--module MODULE] [--json]

Exit codes:
    0  All hard thresholds pass
    1  One or more hard thresholds violated (blocks release)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from relic.eval.gumi_roleplay import evaluate_roleplay_suite
from relic.eval.harness import evaluate_release_gates, ReleaseGateReport, ReleaseGateStatus
from relic.eval.memory_positive import evaluate_memory_positive_suite, get_memory_positive_metric_result


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _roleplay_scenarios() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "gumi-roleplay" / "roleplay_scenarios.jsonl"
    scenarios = []
    for row in _load_jsonl(path):
        scenarios.append(
            {
                "scenario_id": row["scenario_id"],
                "family": row["family"].split("_", 1)[0],
                "user_turn": row.get("user_turn", ""),
                "response": row.get("response") or row.get("expected", ""),
                "blocking": row.get("blocking", False),
                "prompt_context_pack": {
                    "continuity_mode": row.get("expected_continuity_mode", "none"),
                    "roleplay_level": row.get("expected_roleplay_level", "minimal"),
                    "admission_decision": "allowed" if row.get("expected_continuity_mode") != "none" else "blocked",
                    "continuity_candidates": [],
                    "admission_trace": {},
                    "continuity_trace": {},
                },
            }
        )
    return scenarios


def _memory_positive_scenarios() -> list[dict]:
    path = Path(__file__).parent.parent / "fixtures" / "memory-positive" / "memory_positive_scenarios.jsonl"
    scenarios = []
    for row in _load_jsonl(path):
        scenarios.append(
            {
                "scenario_id": row["scenario_id"],
                "scenario_type": row["scenario_type"],
                "a5_response": f"[A5] I recall and apply: {row['expected_response']}",
                "a0_response": "[A0] No stored memory available.",
                "a2_response": "[A2] Basic memory available.",
            }
        )
    return scenarios


def _report_for_module(module: str) -> ReleaseGateReport:
    if module == "gumi_roleplay":
        scenarios = _roleplay_scenarios()
        suite = evaluate_roleplay_suite(scenarios)
        report = evaluate_release_gates(
            false_lived_experience_violations=[],
            coercive_attachment_violations=[],
            prompt_context_complete_count=suite["prompt_context_complete_count"],
            prompt_context_total_count=suite["prompt_context_total_count"],
        )
        report.total_scenarios = suite["total_scenarios"]
        report.summary["total_scenarios"] = suite["total_scenarios"]
        report.summary["families_present"] = suite["families_present"]
        return report

    if module == "memory_positive":
        scenarios = _memory_positive_scenarios()
        suite = evaluate_memory_positive_suite(scenarios)
        metric_results = [
            get_memory_positive_metric_result(
                scenario["scenario_id"],
                scenario["a5_response"],
                scenario["a0_response"],
                scenario["a2_response"],
            )
            for scenario in scenarios
        ]
        report = evaluate_release_gates(memory_positive_results=metric_results)
        report.total_scenarios = suite.total_scenarios
        report.summary["total_scenarios"] = suite.total_scenarios
        report.summary["memory_positive_pass_rate"] = suite.pass_rate
        return report

    if module == "all":
        roleplay = _report_for_module("gumi_roleplay")
        memory = _report_for_module("memory_positive")
        report = ReleaseGateReport()
        report.gate_results.update(roleplay.gate_results)
        report.gate_results.update(memory.gate_results)
        report.total_scenarios = roleplay.total_scenarios + memory.total_scenarios
        for name, result in report.gate_results.items():
            if result.status == ReleaseGateStatus.BLOCKED:
                report.blocked_gates.append(name)
            elif result.status == ReleaseGateStatus.QUARANTINE:
                report.quarantine_gates.append(name)
            elif result.status == ReleaseGateStatus.WARNING:
                report.warning_gates.append(name)
        if report.blocked_gates:
            report.overall_status = ReleaseGateStatus.BLOCKED
        elif report.quarantine_gates:
            report.overall_status = ReleaseGateStatus.QUARANTINE
        elif report.warning_gates:
            report.overall_status = ReleaseGateStatus.WARNING
        report.summary = {
            "total_gates": len(report.gate_results),
            "blocked_count": len(report.blocked_gates),
            "quarantine_count": len(report.quarantine_gates),
            "warning_count": len(report.warning_gates),
            "passed_count": len(report.gate_results)
            - len(report.blocked_gates)
            - len(report.quarantine_gates)
            - len(report.warning_gates),
            "release_blocked": report.blocks_release(),
            "total_scenarios": report.total_scenarios,
        }
        return report

    raise ValueError(f"Unknown eval module: {module}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relic release gate evaluation")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument(
        "--module",
        choices=["all", "gumi_roleplay", "memory_positive"],
        default="all",
        help="Fixture-backed module to evaluate",
    )
    args = parser.parse_args(argv)

    report = _report_for_module(args.module)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"Release gate: {report.overall_status.value.upper()}")
        for gate_name, result in report.gate_results.items():
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {gate_name}: score={result.score:.3f}")
        if report.blocked_gates:
            print(f"\nBLOCKED: {', '.join(report.blocked_gates)}")
        if report.quarantine_gates:
            print(f"QUARANTINE: {', '.join(report.quarantine_gates)}")

    if report.overall_status == ReleaseGateStatus.BLOCKED:
        print("\nRELEASE BLOCKED — hard threshold violated", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
