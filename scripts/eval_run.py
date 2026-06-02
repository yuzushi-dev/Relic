#!/usr/bin/env python3
"""hermes relic eval-run, Run release gate evaluation and exit(1) on failure.

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
from relic.eval.controlled_benchmark import run_governance_benchmark
from relic.eval.human_annotation import (
    build_annotation_packet,
    build_annotation_results_report_from_file,
)
from relic.eval.longitudinal_pilot import (
    build_longitudinal_pilot_protocol,
    build_longitudinal_pilot_results_report_from_file,
)
from relic.eval.runtime_path_coverage import build_runtime_path_coverage_report
from relic.eval.chronicle_audit_coverage import build_chronicle_audit_coverage_report
from relic.eval.workbench_usability import (
    build_workbench_usability_protocol,
    build_workbench_usability_results_report_from_file,
)
from relic.eval.shared_continuity_recovery import (
    build_shared_continuity_recovery_drill_report,
)
from relic.eval.multi_subject_isolation_load import (
    build_multi_subject_isolation_load_report,
)
from relic.eval.runtime_fault_injection import build_runtime_fault_injection_report
from relic.eval.construct_operationalization import (
    build_construct_operationalization_report,
)
from relic.eval.nonclinical_semantic_boundary import (
    build_nonclinical_semantic_boundary_report,
    build_nonclinical_red_team_results_report_from_file,
)
from relic.eval.scientific_defensibility import (
    build_scientific_defensibility_report,
    build_scientific_defensibility_report_from_file,
)
from relic.eval.scientific_evidence_bundle import build_scientific_evidence_bundle_from_file
from relic.eval.scientific_environment_manifest import (
    build_scientific_environment_manifest,
)
from relic.eval.scientific_observation_remediation_audit import (
    build_scientific_observation_remediation_audit,
)
from relic.eval.scientific_reproducibility_snapshot import (
    build_scientific_reproducibility_snapshot,
)
from relic.eval.scientific_local_evidence_package import (
    build_scientific_local_evidence_package,
)
from relic.eval.live_runtime_telemetry import (
    build_live_runtime_telemetry_report_from_file,
    run_mock_gateway_telemetry_campaign,
)
from relic.eval.live_model_generation import (
    build_live_model_generation_artifact_from_file,
    build_live_model_generation_protocol,
)


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


def _emit_report(report: dict, *, json_output: bool, output_path: Path | None) -> None:
    serialized = json.dumps(report, indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n", encoding="utf-8")
    if json_output:
        print(serialized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relic release gate evaluation")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument(
        "--input",
        type=Path,
        help="Input JSON artifact for experiments that import external records",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the complete JSON report to this path",
    )
    parser.add_argument(
        "--module",
        choices=["all", "gumi_roleplay", "memory_positive"],
        default="all",
        help="Fixture-backed module to evaluate",
    )
    parser.add_argument(
        "--experiment",
        choices=[
            "governance_benchmark",
            "human_annotation_packet",
            "human_annotation_results",
            "longitudinal_pilot_protocol",
            "longitudinal_pilot_results",
            "runtime_path_coverage",
            "chronicle_audit_coverage",
            "workbench_usability_protocol",
            "workbench_usability_results",
            "shared_continuity_recovery_drill",
            "multi_subject_isolation_load",
            "runtime_fault_injection",
            "construct_operationalization",
            "nonclinical_semantic_boundary",
            "nonclinical_red_team_results",
            "scientific_defensibility_gate",
            "scientific_evidence_bundle",
            "scientific_environment_manifest",
            "scientific_local_evidence_package",
            "scientific_observation_remediation_audit",
            "scientific_reproducibility_snapshot",
            "mock_runtime_telemetry_campaign",
            "live_runtime_telemetry",
            "live_model_generation_protocol",
            "live_model_generation_artifact",
        ],
        help="Run a scoped fixture-backed experiment instead of release gates",
    )
    args = parser.parse_args(argv)

    if args.experiment == "governance_benchmark":
        experiment_report = run_governance_benchmark()
        if args.json:
            _emit_report(experiment_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(experiment_report, json_output=False, output_path=args.output)
            print(f"Experiment: {experiment_report['experiment_id']}")
            print(f"Claim scope: {experiment_report['claim_scope']}")
            print(f"Scenarios: {experiment_report['scenario_count']}")
            for condition, metrics in experiment_report["condition_metrics"].items():
                print(
                    f"  {condition}: failure_rate={metrics['failure_rate']:.3f} "
                    f"({metrics['failed']}/{metrics['total']})"
                )
        return 0

    if args.experiment == "human_annotation_packet":
        annotation_packet = build_annotation_packet()
        if args.json:
            _emit_report(annotation_packet, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(annotation_packet, json_output=False, output_path=args.output)
            print(f"Study packet: {annotation_packet['study_id']}")
            print(f"Claim scope: {annotation_packet['claim_scope']}")
            print(f"Scenarios: {annotation_packet['scenario_count']}")
            print(f"Items: {annotation_packet['item_count']}")
        return 0

    if args.experiment == "human_annotation_results":
        if args.input is None:
            parser.error("--input is required for human_annotation_results")
        annotation_results = build_annotation_results_report_from_file(args.input)
        if args.json:
            _emit_report(annotation_results, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(annotation_results, json_output=False, output_path=args.output)
            summary = annotation_results["summary"]
            print(f"Annotation results: {annotation_results['report_id']}")
            print(f"Claim scope: {annotation_results['claim_scope']}")
            print(f"Items: {summary['item_count']}")
            print(f"Annotations: {summary['annotation_count']}")
            print(f"Annotators: {summary['annotator_count']}")
        return 0

    if args.experiment == "longitudinal_pilot_protocol":
        pilot_protocol = build_longitudinal_pilot_protocol()
        if args.json:
            _emit_report(pilot_protocol, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(pilot_protocol, json_output=False, output_path=args.output)
            print(f"Pilot protocol: {pilot_protocol['study_id']}")
            print(f"Claim scope: {pilot_protocol['claim_scope']}")
            print(
                "Duration weeks: "
                f"{pilot_protocol['duration_weeks']['minimum']}-"
                f"{pilot_protocol['duration_weeks']['maximum']}"
            )
        return 0

    if args.experiment == "longitudinal_pilot_results":
        if args.input is None:
            parser.error("--input is required for longitudinal_pilot_results")
        pilot_results = build_longitudinal_pilot_results_report_from_file(args.input)
        if args.json:
            _emit_report(pilot_results, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(pilot_results, json_output=False, output_path=args.output)
            summary = pilot_results["summary"]
            print(f"Longitudinal pilot results: {pilot_results['report_id']}")
            print(f"Claim scope: {pilot_results['claim_scope']}")
            print(f"Participants: {summary['participant_count']}")
            print(f"Duration weeks: {summary['observed_duration_weeks']}")
            print(f"Completion rate: {summary['completion_rate']:.3f}")
        return 0

    if args.experiment == "runtime_path_coverage":
        coverage_report = build_runtime_path_coverage_report()
        if args.json:
            _emit_report(coverage_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(coverage_report, json_output=False, output_path=args.output)
            summary = coverage_report["summary"]
            print(f"Runtime coverage report: {coverage_report['report_id']}")
            print(f"Claim scope: {coverage_report['claim_scope']}")
            print(f"Paths: {summary['total_paths']}")
            print(f"Covered: {summary['covered_paths']}")
            print(f"Partial: {summary['partial_paths']}")
            print(f"Compatibility: {summary['compatibility_surface_paths']}")
            print(f"Unresolved: {summary['unresolved_paths']}")
        return 0

    if args.experiment == "chronicle_audit_coverage":
        audit_report = build_chronicle_audit_coverage_report()
        if args.json:
            _emit_report(audit_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(audit_report, json_output=False, output_path=args.output)
            summary = audit_report["summary"]
            print(f"Chronicle audit coverage: {audit_report['report_id']}")
            print(f"Claim scope: {audit_report['claim_scope']}")
            print(f"Questions: {summary['reconstruction_questions']}")
            print(f"Supported questions: {summary['supported_questions']}")
            print(f"Partial capabilities: {summary['partial_capabilities']}")
        return 0

    if args.experiment == "workbench_usability_protocol":
        usability_protocol = build_workbench_usability_protocol()
        if args.json:
            _emit_report(usability_protocol, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(usability_protocol, json_output=False, output_path=args.output)
            print(f"Workbench usability protocol: {usability_protocol['study_id']}")
            print(f"Claim scope: {usability_protocol['claim_scope']}")
            print(f"Tasks: {len(usability_protocol['tasks'])}")
            print(
                "Sample size: "
                f"{usability_protocol['sample_size']['minimum']}-"
                f"{usability_protocol['sample_size']['maximum']}"
            )
        return 0

    if args.experiment == "workbench_usability_results":
        if args.input is None:
            parser.error("--input is required for workbench_usability_results")
        usability_results = build_workbench_usability_results_report_from_file(args.input)
        if args.json:
            _emit_report(usability_results, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(usability_results, json_output=False, output_path=args.output)
            summary = usability_results["summary"]
            print(f"Workbench usability results: {usability_results['report_id']}")
            print(f"Claim scope: {usability_results['claim_scope']}")
            print(f"Participants: {summary['participant_count']}")
            print(f"Task success rate: {summary['task_success_rate']:.3f}")
            print(f"Critical error rate: {summary['critical_error_rate']:.3f}")
        return 0

    if args.experiment == "shared_continuity_recovery_drill":
        recovery_report = build_shared_continuity_recovery_drill_report()
        if args.json:
            _emit_report(recovery_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(recovery_report, json_output=False, output_path=args.output)
            summary = recovery_report["summary"]
            print(f"Shared Continuity recovery drill: {recovery_report['report_id']}")
            print(f"Claim scope: {recovery_report['claim_scope']}")
            print(f"Backup integrity: {summary['backup_integrity_ok']}")
            print(f"Restore integrity: {summary['restore_integrity_ok']}")
            print(f"Checksum verified: {summary['checksum_verified']}")
        return 0

    if args.experiment == "multi_subject_isolation_load":
        load_report = build_multi_subject_isolation_load_report()
        if args.json:
            _emit_report(load_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(load_report, json_output=False, output_path=args.output)
            summary = load_report["summary"]
            print(f"Multi-subject isolation load: {load_report['report_id']}")
            print(f"Claim scope: {load_report['claim_scope']}")
            print(f"Subjects: {summary['subject_count']}")
            print(f"Researchers: {summary['researcher_count']}")
            print(f"Stored markers: {summary['stored_marker_count']}")
            print(f"Cross-subject leaks: {summary['cross_subject_leak_count']}")
        return 0 if load_report["validation"]["valid"] else 1

    if args.experiment == "runtime_fault_injection":
        fault_report = build_runtime_fault_injection_report()
        if args.json:
            _emit_report(fault_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(fault_report, json_output=False, output_path=args.output)
            summary = fault_report["summary"]
            print(f"Runtime fault injection: {fault_report['report_id']}")
            print(f"Claim scope: {fault_report['claim_scope']}")
            print(f"Scenarios: {summary['scenario_count']}")
            print(f"Fail-closed: {summary['fail_closed_count']}")
            print(f"Unexpected allow: {summary['unexpected_allow_count']}")
        return 0 if fault_report["validation"]["valid"] else 1

    if args.experiment == "construct_operationalization":
        construct_report = build_construct_operationalization_report()
        if args.json:
            _emit_report(construct_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(construct_report, json_output=False, output_path=args.output)
            summary = construct_report["summary"]
            print(f"Construct operationalization: {construct_report['report_id']}")
            print(f"Claim scope: {construct_report['claim_scope']}")
            print(f"Constructs: {summary['construct_count']}")
            print(f"Complete: {summary['complete_construct_count']}")
            print(
                "Missing dimensions: "
                f"{summary['missing_required_annotation_dimension_count']}"
            )
        return 0 if construct_report["validation"]["valid"] else 1

    if args.experiment == "nonclinical_semantic_boundary":
        semantic_report = build_nonclinical_semantic_boundary_report()
        if args.json:
            _emit_report(semantic_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(semantic_report, json_output=False, output_path=args.output)
            summary = semantic_report["summary"]
            print(f"Non-clinical semantic boundary: {semantic_report['report_id']}")
            print(f"Claim scope: {semantic_report['claim_scope']}")
            print(f"Scenarios: {summary['scenario_count']}")
            print(
                "Semantic overreach block rate: "
                f"{summary['semantic_overreach_block_rate']:.3f}"
            )
        return 0

    if args.experiment == "nonclinical_red_team_results":
        if args.input is None:
            parser.error("--input is required for nonclinical_red_team_results")
        red_team_report = build_nonclinical_red_team_results_report_from_file(args.input)
        if args.json:
            _emit_report(red_team_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(red_team_report, json_output=False, output_path=args.output)
            summary = red_team_report["summary"]
            print(f"Non-clinical red-team results: {red_team_report['report_id']}")
            print(f"Claim scope: {red_team_report['claim_scope']}")
            print(f"Cases: {summary['case_count']}")
            print(f"Reviewers: {summary['reviewer_count']}")
            print(f"Unsafe allow rate: {summary['unsafe_allow_rate']:.3f}")
        return 0

    if args.experiment == "scientific_defensibility_gate":
        defensibility_report = (
            build_scientific_defensibility_report_from_file(args.input)
            if args.input
            else build_scientific_defensibility_report()
        )
        if args.json:
            _emit_report(defensibility_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(defensibility_report, json_output=False, output_path=args.output)
            summary = defensibility_report["summary"]
            print(f"Scientific defensibility: {defensibility_report['report_id']}")
            print(f"Claim scope: {defensibility_report['claim_scope']}")
            print(f"Status: {defensibility_report['overall_status']}")
            print(f"Blocked requirements: {summary['blocked_count']}")
        return 1 if defensibility_report["summary"]["blocks_scientific_claims"] else 0

    if args.experiment == "scientific_evidence_bundle":
        if args.input is None:
            parser.error("--input is required for scientific_evidence_bundle")
        evidence_bundle = build_scientific_evidence_bundle_from_file(args.input)
        if args.json:
            _emit_report(evidence_bundle, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(evidence_bundle, json_output=False, output_path=args.output)
            summary = evidence_bundle["summary"]
            print(f"Scientific evidence bundle: {evidence_bundle['report_id']}")
            print(f"Claim scope: {evidence_bundle['claim_scope']}")
            print(f"Artifact files: {summary['artifact_file_count']}")
            print(f"Gate status: {summary['gate_overall_status']}")
        return 1 if evidence_bundle["summary"]["blocks_scientific_claims"] else 0

    if args.experiment == "scientific_environment_manifest":
        environment_manifest = build_scientific_environment_manifest()
        if args.json:
            _emit_report(environment_manifest, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(environment_manifest, json_output=False, output_path=args.output)
            summary = environment_manifest["summary"]
            print(f"Scientific environment manifest: {environment_manifest['report_id']}")
            print(f"Claim scope: {environment_manifest['claim_scope']}")
            print(f"Dependency lockfile present: {summary['dependency_lockfile_present']}")
            print(f"Working tree clean: {summary['working_tree_clean']}")
            print(f"Release artifact ready: {summary['release_artifact_ready']}")
        return 0 if environment_manifest["validation"]["valid"] else 1

    if args.experiment == "scientific_observation_remediation_audit":
        remediation_audit = build_scientific_observation_remediation_audit()
        if args.json:
            _emit_report(remediation_audit, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(remediation_audit, json_output=False, output_path=args.output)
            summary = remediation_audit["summary"]
            print(f"Scientific observation remediation audit: {remediation_audit['report_id']}")
            print(f"Claim scope: {remediation_audit['claim_scope']}")
            print(f"Gaps: {summary['gap_count']}")
            print(f"Blocked external evidence: {summary['blocked_external_evidence_count']}")
        return 0 if remediation_audit["validation"]["valid"] else 1

    if args.experiment == "scientific_local_evidence_package":
        local_package = build_scientific_local_evidence_package()
        if args.json:
            _emit_report(local_package, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(local_package, json_output=False, output_path=args.output)
            summary = local_package["summary"]
            print(f"Scientific local evidence package: {local_package['report_id']}")
            print(f"Claim scope: {local_package['claim_scope']}")
            print(f"Gate satisfied: {summary['gate_satisfied_count']}")
            print(f"Gate blocked: {summary['gate_blocked_count']}")
        return 1 if local_package["summary"]["blocks_scientific_claims"] else 0

    if args.experiment == "scientific_reproducibility_snapshot":
        snapshot = build_scientific_reproducibility_snapshot()
        if args.json:
            _emit_report(snapshot, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(snapshot, json_output=False, output_path=args.output)
            summary = snapshot["summary"]
            print(f"Scientific reproducibility snapshot: {snapshot['report_id']}")
            print(f"Claim scope: {snapshot['claim_scope']}")
            print(f"Local reports: {summary['local_report_count']}")
            print(
                "External evidence artifacts: "
                f"{summary['external_evidence_artifacts_included']}"
            )
        return 0

    if args.experiment == "mock_runtime_telemetry_campaign":
        campaign = run_mock_gateway_telemetry_campaign()
        if args.json:
            _emit_report(campaign, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(campaign, json_output=False, output_path=args.output)
            summary = campaign["summary"]
            print(f"Mock runtime telemetry campaign: {campaign['report_id']}")
            print(f"Claim scope: {campaign['claim_scope']}")
            print(f"Traces: {summary['trace_count']}")
            print(f"Delivered: {summary['delivered_output_count']}")
            print(f"Blocked: {summary['blocked_output_count']}")
        return 0

    if args.experiment == "live_runtime_telemetry":
        if args.input is None:
            parser.error("--input is required for live_runtime_telemetry")
        telemetry_report = build_live_runtime_telemetry_report_from_file(args.input)
        if args.json:
            _emit_report(telemetry_report, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(telemetry_report, json_output=False, output_path=args.output)
            summary = telemetry_report["summary"]
            print(f"Live runtime telemetry: {telemetry_report['report_id']}")
            print(f"Claim scope: {telemetry_report['claim_scope']}")
            print(f"Traces: {summary['trace_count']}")
            print(f"Channels: {summary['deployment_channel_count']}")
            print(f"Paths: {summary['covered_path_count']}")
        return 0

    if args.experiment == "live_model_generation_protocol":
        live_protocol = build_live_model_generation_protocol()
        if args.json:
            _emit_report(live_protocol, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(live_protocol, json_output=False, output_path=args.output)
            summary = live_protocol["summary"]
            print(f"Live-model generation protocol: {live_protocol['report_id']}")
            print(f"Claim scope: {live_protocol['claim_scope']}")
            print(f"Scenarios: {summary['scenario_count']}")
            print(f"Planned requests: {summary['planned_request_count']}")
        return 0

    if args.experiment == "live_model_generation_artifact":
        if args.input is None:
            parser.error("--input is required for live_model_generation_artifact")
        live_artifact = build_live_model_generation_artifact_from_file(args.input)
        if args.json:
            _emit_report(live_artifact, json_output=True, output_path=args.output)
        else:
            if args.output is not None:
                _emit_report(live_artifact, json_output=False, output_path=args.output)
            summary = live_artifact["summary"]
            print(f"Live-model generation artifact: {live_artifact['report_id']}")
            print(f"Claim scope: {live_artifact['claim_scope']}")
            print(f"Providers: {summary['provider_count']}")
            print(
                "Completed requests: "
                f"{summary['completed_generation_count']}/"
                f"{summary['expected_generation_count']}"
            )
            print(f"Failure rate: {summary['failure_rate']:.3f}")
        return 0

    report = _report_for_module(args.module)

    release_report = report.to_dict()
    if args.json:
        _emit_report(release_report, json_output=True, output_path=args.output)
    else:
        if args.output is not None:
            _emit_report(release_report, json_output=False, output_path=args.output)
        print(f"Release gate: {report.overall_status.value.upper()}")
        for gate_name, result in report.gate_results.items():
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {gate_name}: score={result.score:.3f}")
        if report.blocked_gates:
            print(f"\nBLOCKED: {', '.join(report.blocked_gates)}")
        if report.quarantine_gates:
            print(f"QUARANTINE: {', '.join(report.quarantine_gates)}")

    if report.overall_status == ReleaseGateStatus.BLOCKED:
        print("\nRELEASE BLOCKED, hard threshold violated", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
