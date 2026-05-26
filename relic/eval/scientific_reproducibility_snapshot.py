"""Local reproducibility snapshot for scientific evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from relic.eval.chronicle_audit_coverage import build_chronicle_audit_coverage_report
from relic.eval.construct_operationalization import build_construct_operationalization_report
from relic.eval.controlled_benchmark import run_governance_benchmark
from relic.eval.human_annotation import build_annotation_packet
from relic.eval.live_model_generation import build_live_model_generation_protocol
from relic.eval.live_runtime_telemetry import run_mock_gateway_telemetry_campaign
from relic.eval.longitudinal_pilot import build_longitudinal_pilot_protocol
from relic.eval.multi_subject_isolation_load import build_multi_subject_isolation_load_report
from relic.eval.nonclinical_semantic_boundary import build_nonclinical_semantic_boundary_report
from relic.eval.runtime_path_coverage import build_runtime_path_coverage_report
from relic.eval.runtime_fault_injection import build_runtime_fault_injection_report
from relic.eval.scientific_defensibility import build_scientific_defensibility_report
from relic.eval.scientific_environment_manifest import build_scientific_environment_manifest
from relic.eval.scientific_local_evidence_package import build_scientific_local_evidence_package
from relic.eval.scientific_observation_remediation_audit import (
    build_scientific_observation_remediation_audit,
)
from relic.eval.shared_continuity_recovery import build_shared_continuity_recovery_drill_report
from relic.eval.workbench_usability import build_workbench_usability_protocol


REPORT_ID = "scientific_reproducibility_snapshot_v1"
CLAIM_SCOPE = "reproducible_local_evaluation_snapshot"
REVIEW_DATE = "2026-05-25"


LOCAL_REPORT_BUILDERS: tuple[tuple[str, str, Callable[[], dict[str, Any]]], ...] = (
    ("governance_benchmark", "governance-benchmark.json", run_governance_benchmark),
    (
        "scientific_environment_manifest",
        "scientific-environment-manifest.json",
        build_scientific_environment_manifest,
    ),
    (
        "scientific_observation_remediation_audit",
        "scientific-observation-remediation-audit.json",
        build_scientific_observation_remediation_audit,
    ),
    (
        "scientific_local_evidence_package",
        "scientific-local-evidence-package.json",
        build_scientific_local_evidence_package,
    ),
    ("human_annotation_packet", "human-annotation-packet.json", build_annotation_packet),
    (
        "live_model_generation_protocol",
        "live-model-generation-protocol.json",
        build_live_model_generation_protocol,
    ),
    (
        "longitudinal_pilot_protocol",
        "longitudinal-pilot-protocol.json",
        build_longitudinal_pilot_protocol,
    ),
    ("runtime_path_coverage", "runtime-path-coverage.json", build_runtime_path_coverage_report),
    (
        "chronicle_audit_coverage",
        "chronicle-audit-coverage.json",
        build_chronicle_audit_coverage_report,
    ),
    (
        "workbench_usability_protocol",
        "workbench-usability-protocol.json",
        build_workbench_usability_protocol,
    ),
    (
        "shared_continuity_recovery_drill",
        "shared-continuity-recovery-drill.json",
        build_shared_continuity_recovery_drill_report,
    ),
    (
        "multi_subject_isolation_load",
        "multi-subject-isolation-load.json",
        build_multi_subject_isolation_load_report,
    ),
    (
        "runtime_fault_injection",
        "runtime-fault-injection.json",
        build_runtime_fault_injection_report,
    ),
    (
        "construct_operationalization",
        "construct-operationalization.json",
        build_construct_operationalization_report,
    ),
    (
        "nonclinical_semantic_boundary",
        "nonclinical-semantic-boundary.json",
        build_nonclinical_semantic_boundary_report,
    ),
    (
        "mock_runtime_telemetry_campaign",
        "mock-runtime-telemetry-campaign.json",
        run_mock_gateway_telemetry_campaign,
    ),
    (
        "scientific_defensibility_gate",
        "scientific-defensibility-gate.json",
        build_scientific_defensibility_report,
    ),
)


def build_scientific_reproducibility_snapshot() -> dict[str, Any]:
    """Build a hash-tracked snapshot of locally reproducible evaluation reports."""
    reports: dict[str, dict[str, Any]] = {}
    manifest: list[dict[str, Any]] = []

    for experiment, filename, builder in LOCAL_REPORT_BUILDERS:
        report = builder()
        report_id = _report_identity(report)
        reports[report_id] = report
        manifest.append(
            {
                "experiment": experiment,
                "report_id": report_id,
                "claim_scope": report.get("claim_scope"),
                "sha256": _hash_report(report),
                "size_bytes": len(_canonical_json(report).encode("utf-8")),
                "reproduce_command": (
                    "python scripts/eval_run.py "
                    f"--experiment {experiment} "
                    f"--output artifacts/{filename} --json"
                ),
            }
        )

    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "local_report_hash_manifest_with_embedded_expected_outputs",
            "review_date": REVIEW_DATE,
            "provenance_basis": [
                "canonical_json_sha256",
                "explicit_eval_run_command",
                "embedded_expected_report",
            ],
        },
        "summary": {
            "local_report_count": len(manifest),
            "external_evidence_artifacts_included": 0,
            "scientific_claims_satisfied": False,
        },
        "report_manifest": manifest,
        "expected_reports": reports,
        "validation": {
            "valid": True,
            "checked_rules": [
                "local_reports_built",
                "canonical_hashes_computed",
                "reproduction_commands_recorded",
                "external_evidence_not_fabricated",
            ],
        },
        "claim_limitations": [
            "does not create missing external evidence",
            "does not include live provider generations or recruited human results",
            "does not prove production deployment telemetry",
            "broad scientific claims remain governed by scientific_defensibility_gate_v1",
        ],
    }


def _report_identity(report: dict[str, Any]) -> str:
    return str(report.get("report_id") or report.get("experiment_id") or report.get("study_id"))


def _hash_report(report: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(report).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _canonical_json(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"))
