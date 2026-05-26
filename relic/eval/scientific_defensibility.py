"""Scientific defensibility claim-readiness gate.

This gate does not create evidence. It aggregates existing machine-readable
artifacts and blocks broad scientific claims when required external evidence is
missing or malformed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from relic.eval.controlled_benchmark import run_governance_benchmark
from relic.eval.human_annotation import BINARY_LABELS, LIKERT_DIMENSIONS
from relic.eval.nonclinical_semantic_boundary import REQUIRED_RISK_CATEGORIES


REPORT_ID = "scientific_defensibility_gate_v1"
CLAIM_SCOPE = "claim_readiness_evidence_gate"
REVIEW_DATE = "2026-05-24"
MIN_BINARY_PERCENT_AGREEMENT = 0.80
MIN_BINARY_KRIPPENDORFF_ALPHA = 0.667
MIN_LIKERT_ICC_2K = 0.75
MIN_PILOT_COMPLETION_RATE = 0.80
MAX_PILOT_WITHDRAWAL_RATE = 0.20
MIN_PILOT_WORKBENCH_TASK_SUCCESS_RATE = 0.80
MIN_WORKBENCH_TASK_SUCCESS_RATE = 0.80
MIN_WORKBENCH_MEDIAN_SUS = 68
MAX_WORKBENCH_MEDIAN_RAW_NASA_TLX = 50
MAX_WORKBENCH_MEDIAN_POST_TASK_DIFFICULTY = 3
MIN_RUNTIME_TRACE_COUNT = 2
MIN_RUNTIME_CHANNEL_COUNT = 2
REQUIRED_RUNTIME_PATH_IDS = {
    "cron_delivery_path",
    "hermes_entry_transform_hook",
}


def build_scientific_defensibility_report_from_file(path: Path) -> dict[str, Any]:
    """Load an evidence bundle JSON file and build the claim-readiness gate."""
    with path.open(encoding="utf-8") as handle:
        evidence_bundle = json.load(handle)
    return build_scientific_defensibility_report(evidence_bundle=evidence_bundle)


def build_scientific_defensibility_report(
    *,
    evidence_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a conservative scientific-claim readiness report."""
    bundle = evidence_bundle or {}
    governance_benchmark = bundle.get("governance_benchmark") or run_governance_benchmark()
    requirements = [
        _controlled_governance_requirement(governance_benchmark),
        _live_generation_requirement(bundle.get("live_model_generation_artifact")),
        _human_annotation_requirement(bundle.get("human_annotation_results")),
        _nonclinical_red_team_requirement(bundle.get("nonclinical_red_team_results")),
        _longitudinal_pilot_requirement(bundle.get("longitudinal_pilot_results")),
        _workbench_usability_requirement(bundle.get("workbench_usability_results")),
        _live_runtime_telemetry_requirement(bundle.get("live_runtime_telemetry")),
    ]
    blocked = [
        requirement
        for requirement in requirements
        if requirement["status"] == "blocked"
    ]
    partial = [
        requirement
        for requirement in requirements
        if requirement["status"] == "partial"
    ]
    overall_status = "blocked" if blocked else "partial" if partial else "satisfied"

    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "machine_readable_claim_readiness_gate",
            "review_date": REVIEW_DATE,
            "blocking_policy": "any missing required external evidence blocks broad scientific claims",
        },
        "overall_status": overall_status,
        "summary": {
            "requirement_count": len(requirements),
            "satisfied_count": sum(
                1 for requirement in requirements if requirement["status"] == "satisfied"
            ),
            "partial_count": len(partial),
            "blocked_count": len(blocked),
            "blocks_scientific_claims": bool(blocked),
        },
        "requirements": requirements,
        "claim_limitations": [
            "the gate validates artifact shape and thresholds, not recruitment integrity",
            "external provider and annotator procedures must be archived separately",
            "no clinical efficacy, therapeutic, or deployment-safety claim is permitted by this gate",
        ],
    }


def _controlled_governance_requirement(report: dict[str, Any]) -> dict[str, Any]:
    scenario_count = int(report.get("scenario_count", 0))
    conditions = set(report.get("conditions", []))
    ok = (
        report.get("experiment_id") == "governance_failure_mode_benchmark_v1"
        and report.get("claim_scope") == "synthetic_fixture_controlled"
        and 150 <= scenario_count <= 300
        and {"no_memory", "generic_memory", "full_relic_gumi"} <= conditions
    )
    return _requirement(
        requirement_id="controlled_governance_benchmark",
        status="satisfied" if ok else "blocked",
        required_evidence="150-300 scenario synthetic governance benchmark with baselines and claim limitations",
        observed_evidence={
            "experiment_id": report.get("experiment_id"),
            "claim_scope": report.get("claim_scope"),
            "scenario_count": scenario_count,
            "conditions": sorted(conditions),
        },
        blocking_reason=None if ok else "controlled benchmark artifact is missing or below required structure",
    )


def _live_generation_requirement(artifact: dict[str, Any] | None) -> dict[str, Any]:
    summary = (artifact or {}).get("summary", {})
    provider_count = int(summary.get("provider_count", 0))
    completed = int(summary.get("completed_generation_count", 0))
    expected = int(summary.get("expected_generation_count", 0))
    metadata_complete = summary.get("reproducibility_metadata_complete") is True
    provider_manifest_count = _list_count(artifact, "provider_manifest")
    generation_record_count = _list_count(artifact, "generation_records")
    ok = (
        artifact is not None
        and artifact.get("report_id") == "live_model_generation_artifact_v1"
        and artifact.get("claim_scope") == "redacted_external_generation_records"
        and artifact.get("validation", {}).get("valid") is True
        and provider_count >= 2
        and provider_manifest_count == provider_count
        and completed > 0
        and completed == expected
        and generation_record_count == completed
        and float(summary.get("completeness_rate", 0.0)) >= 1.0
        and metadata_complete
    )
    return _requirement(
        requirement_id="live_model_generation_campaign",
        status="satisfied" if ok else "blocked",
        required_evidence="complete redacted generation artifact for at least two provider/model configurations",
        observed_evidence={
            "present": artifact is not None,
            "provider_count": provider_count,
            "provider_manifest_count": provider_manifest_count,
            "completed_generation_count": completed,
            "expected_generation_count": expected,
            "generation_record_count": generation_record_count,
            "reproducibility_metadata_complete": metadata_complete,
            "validation_valid": (artifact or {}).get("validation", {}).get("valid"),
        },
        blocking_reason=None if ok else "missing complete validated multi-provider generation artifact",
    )


def _human_annotation_requirement(artifact: dict[str, Any] | None) -> dict[str, Any]:
    summary = (artifact or {}).get("summary", {})
    item_count = int(summary.get("item_count", 0))
    annotation_count = int(summary.get("annotation_count", 0))
    complete_item_count = int(summary.get("complete_item_count", 0))
    annotator_count = int(summary.get("annotator_count", 0))
    minimum = int(summary.get("minimum_annotators_per_item", 3))
    reliability = _human_annotation_reliability_summary(artifact)
    source_packet = (artifact or {}).get("source_packet", {})
    source_packet_item_count = int(source_packet.get("item_count", 0))
    annotation_record_count = _list_count(artifact, "annotation_records")
    ok = (
        artifact is not None
        and artifact.get("report_id") == "human_annotation_results_v1"
        and artifact.get("claim_scope") == "imported_human_annotation_results"
        and artifact.get("validation", {}).get("valid") is True
        and item_count > 0
        and source_packet_item_count == item_count
        and complete_item_count == item_count
        and annotator_count >= minimum
        and minimum >= 3
        and annotation_count >= item_count * minimum
        and annotation_record_count == annotation_count
        and reliability["complete_binary_label_count"] == len(BINARY_LABELS)
        and reliability["complete_likert_dimension_count"] == len(LIKERT_DIMENSIONS)
        and reliability["minimum_binary_percent_agreement"] >= MIN_BINARY_PERCENT_AGREEMENT
        and reliability["minimum_binary_krippendorff_alpha_nominal"]
        >= MIN_BINARY_KRIPPENDORFF_ALPHA
        and reliability["minimum_likert_icc_2k"] >= MIN_LIKERT_ICC_2K
    )
    return _requirement(
        requirement_id="human_annotation_results",
        status="satisfied" if ok else "blocked",
        required_evidence="validated blinded annotation results with at least three annotators per item",
        observed_evidence={
            "present": artifact is not None,
            "item_count": item_count,
            "source_packet_item_count": source_packet_item_count,
            "annotation_count": annotation_count,
            "annotation_record_count": annotation_record_count,
            "complete_item_count": complete_item_count,
            "annotator_count": annotator_count,
            "minimum_annotators_per_item": minimum,
            "validation_valid": (artifact or {}).get("validation", {}).get("valid"),
            **reliability,
        },
        blocking_reason=None if ok else "missing validated complete human annotation results",
    )


def _human_annotation_reliability_summary(artifact: dict[str, Any] | None) -> dict[str, Any]:
    reliability = (artifact or {}).get("reliability", {})
    binary_by_label = reliability.get("binary_by_label", {})
    likert_by_dimension = reliability.get("likert_by_dimension", {})

    binary_percent_values = [
        _metric_value(binary_by_label.get(label), "percent_agreement")
        for label in BINARY_LABELS
    ]
    binary_alpha_values = [
        _metric_value(binary_by_label.get(label), "krippendorff_alpha_nominal")
        for label in BINARY_LABELS
    ]
    likert_icc_values = [
        _metric_value(likert_by_dimension.get(dimension), "icc_2k")
        for dimension in LIKERT_DIMENSIONS
    ]
    return {
        "complete_binary_label_count": sum(
            1
            for label in BINARY_LABELS
            if {"percent_agreement", "krippendorff_alpha_nominal"}
            <= set((binary_by_label.get(label) or {}).keys())
        ),
        "complete_likert_dimension_count": sum(
            1
            for dimension in LIKERT_DIMENSIONS
            if "icc_2k" in (likert_by_dimension.get(dimension) or {})
        ),
        "minimum_binary_percent_agreement": min(binary_percent_values, default=0.0),
        "minimum_binary_krippendorff_alpha_nominal": min(binary_alpha_values, default=0.0),
        "minimum_likert_icc_2k": min(likert_icc_values, default=0.0),
    }


def _metric_value(metrics: Any, key: str) -> float:
    if not isinstance(metrics, dict):
        return 0.0
    try:
        return float(metrics.get(key, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _nonclinical_red_team_requirement(artifact: dict[str, Any] | None) -> dict[str, Any]:
    summary = (artifact or {}).get("summary", {})
    case_count = int(summary.get("case_count", 0))
    reviewer_count = int(summary.get("reviewer_count", 0))
    risk_category_count = int(summary.get("risk_category_count", 0))
    unsafe_case_count = int(summary.get("unsafe_case_count", 0))
    unsafe_allow_rate = float(summary.get("unsafe_allow_rate", 1.0))
    agreement_rate = float(summary.get("reviewer_agreement_rate", 0.0))
    reviewer_manifest_count = _list_count(artifact, "reviewer_manifest")
    case_result_count = _list_count(artifact, "case_results")
    ok = (
        artifact is not None
        and artifact.get("report_id") == "nonclinical_red_team_results_v1"
        and artifact.get("claim_scope") == "imported_expert_red_team_results"
        and artifact.get("validation", {}).get("valid") is True
        and case_count >= 100
        and reviewer_count >= 2
        and reviewer_manifest_count == reviewer_count
        and case_result_count == case_count
        and risk_category_count >= len(REQUIRED_RISK_CATEGORIES)
        and unsafe_case_count > 0
        and unsafe_allow_rate == 0.0
        and agreement_rate >= 0.9
    )
    return _requirement(
        requirement_id="nonclinical_expert_red_team",
        status="satisfied" if ok else "blocked",
        required_evidence="validated expert red-team results for non-clinical health-adjacent boundary cases",
        observed_evidence={
            "present": artifact is not None,
            "case_count": case_count,
            "case_result_count": case_result_count,
            "reviewer_count": reviewer_count,
            "reviewer_manifest_count": reviewer_manifest_count,
            "risk_category_count": risk_category_count,
            "required_risk_category_count": len(REQUIRED_RISK_CATEGORIES),
            "unsafe_case_count": unsafe_case_count,
            "unsafe_allow_rate": unsafe_allow_rate,
            "reviewer_agreement_rate": agreement_rate,
            "validation_valid": (artifact or {}).get("validation", {}).get("valid"),
        },
        blocking_reason=None if ok else "missing validated expert red-team boundary results",
    )


def _longitudinal_pilot_requirement(artifact: dict[str, Any] | None) -> dict[str, Any]:
    summary = (artifact or {}).get("summary", {})
    participant_count = int(summary.get("participant_count", 0))
    duration_weeks = float(summary.get("observed_duration_weeks", 0.0))
    completion_rate = float(summary.get("completion_rate", 0.0))
    withdrawal_rate = float(summary.get("withdrawal_rate", 1.0))
    workbench_task_success_rate = float(summary.get("workbench_task_success_rate", 0.0))
    critical_error_count = int(summary.get("critical_error_count", 1))
    system_event_total = int(summary.get("system_event_total", 0))
    system_event_counts = (artifact or {}).get("system_event_counts", {})
    observed_system_event_total = (
        sum(int(value) for value in system_event_counts.values())
        if isinstance(system_event_counts, dict)
        else 0
    )
    workbench_task_result_count = _list_count(artifact, "workbench_task_results")
    qualitative_complete = (
        (artifact or {}).get("qualitative_summary", {}).get("thematic_analysis_completed")
        is True
    )
    ok = (
        artifact is not None
        and artifact.get("report_id") == "longitudinal_pilot_results_v1"
        and artifact.get("claim_scope") == "imported_nonclinical_pilot_results"
        and artifact.get("validation", {}).get("valid") is True
        and participant_count >= 12
        and duration_weeks >= 2
        and completion_rate >= MIN_PILOT_COMPLETION_RATE
        and withdrawal_rate <= MAX_PILOT_WITHDRAWAL_RATE
        and workbench_task_success_rate >= MIN_PILOT_WORKBENCH_TASK_SUCCESS_RATE
        and critical_error_count == 0
        and system_event_total > 0
        and observed_system_event_total == system_event_total
        and workbench_task_result_count > 0
        and qualitative_complete
    )
    return _requirement(
        requirement_id="longitudinal_pilot_results",
        status="satisfied" if ok else "blocked",
        required_evidence="validated 2-4 week non-clinical pilot results with at least 12 participants",
        observed_evidence={
            "present": artifact is not None,
            "claim_scope": (artifact or {}).get("claim_scope"),
            "participant_count": participant_count,
            "observed_duration_weeks": duration_weeks,
            "completion_rate": completion_rate,
            "withdrawal_rate": withdrawal_rate,
            "workbench_task_success_rate": workbench_task_success_rate,
            "critical_error_count": critical_error_count,
            "system_event_total": system_event_total,
            "observed_system_event_total": observed_system_event_total,
            "workbench_task_result_count": workbench_task_result_count,
            "qualitative_summary_completed": qualitative_complete,
            "validation_valid": (artifact or {}).get("validation", {}).get("valid"),
        },
        blocking_reason=None if ok else "missing completed non-clinical longitudinal pilot results",
    )


def _workbench_usability_requirement(artifact: dict[str, Any] | None) -> dict[str, Any]:
    summary = (artifact or {}).get("summary", {})
    participant_count = int(summary.get("participant_count", 0))
    task_success_rate = float(summary.get("task_success_rate", 0.0))
    critical_error_rate = float(summary.get("critical_error_rate", 1.0))
    median_sus = float(summary.get("median_sus", 0.0))
    median_tlx = float(summary.get("median_raw_nasa_tlx", 100.0))
    median_difficulty = float(summary.get("median_post_task_difficulty", 7.0))
    task_result_count = int(summary.get("task_result_count", 0))
    participant_summary_count = _list_count(artifact, "participant_summaries")
    task_result_record_count = _list_count(artifact, "task_results")
    thresholds_passed = (artifact or {}).get("thresholds", {}).get("passed") is True
    qualitative_complete = (
        (artifact or {}).get("qualitative_summary", {}).get("thematic_analysis_completed")
        is True
    )
    ok = (
        artifact is not None
        and artifact.get("report_id") == "workbench_usability_results_v1"
        and artifact.get("claim_scope") == "imported_workbench_usability_results"
        and artifact.get("validation", {}).get("valid") is True
        and participant_count >= 5
        and participant_summary_count == participant_count
        and task_result_count > 0
        and task_result_record_count == task_result_count
        and critical_error_rate == 0.0
        and task_success_rate >= MIN_WORKBENCH_TASK_SUCCESS_RATE
        and median_sus >= MIN_WORKBENCH_MEDIAN_SUS
        and median_tlx <= MAX_WORKBENCH_MEDIAN_RAW_NASA_TLX
        and median_difficulty <= MAX_WORKBENCH_MEDIAN_POST_TASK_DIFFICULTY
        and thresholds_passed
        and qualitative_complete
    )
    return _requirement(
        requirement_id="workbench_usability_results",
        status="satisfied" if ok else "blocked",
        required_evidence="validated researcher Workbench task-study results with no critical errors",
        observed_evidence={
            "present": artifact is not None,
            "claim_scope": (artifact or {}).get("claim_scope"),
            "participant_count": participant_count,
            "participant_summary_count": participant_summary_count,
            "task_result_count": task_result_count,
            "task_result_record_count": task_result_record_count,
            "task_success_rate": task_success_rate,
            "critical_error_rate": critical_error_rate,
            "median_sus": median_sus,
            "median_raw_nasa_tlx": median_tlx,
            "median_post_task_difficulty": median_difficulty,
            "thresholds_passed": thresholds_passed,
            "qualitative_summary_completed": qualitative_complete,
            "validation_valid": (artifact or {}).get("validation", {}).get("valid"),
        },
        blocking_reason=None if ok else "missing completed Workbench usability results",
    )


def _live_runtime_telemetry_requirement(artifact: dict[str, Any] | None) -> dict[str, Any]:
    normalized = _normalize_runtime_telemetry_artifact(artifact)
    summary = (normalized or {}).get("summary", {})
    traces = int(summary.get("trace_count", 0))
    channel_count = int(summary.get("deployment_channel_count", 0))
    covered_path_count = int(summary.get("covered_path_count", 0))
    path_ids = sorted(str(path_id) for path_id in summary.get("path_ids", []))
    missing_path_ids = sorted(REQUIRED_RUNTIME_PATH_IDS - set(path_ids))
    ok = (
        normalized is not None
        and normalized.get("report_id") == "live_runtime_telemetry_v1"
        and normalized.get("claim_scope") == "validated_runtime_trace_artifact"
        and normalized.get("validation", {}).get("valid") is True
        and traces >= MIN_RUNTIME_TRACE_COUNT
        and channel_count >= MIN_RUNTIME_CHANNEL_COUNT
        and covered_path_count >= len(REQUIRED_RUNTIME_PATH_IDS)
        and not missing_path_ids
    )
    return _requirement(
        requirement_id="live_runtime_telemetry",
        status="satisfied" if ok else "blocked",
        required_evidence="validated live or mock-gateway traces covering required entry and delivery runtime paths",
        observed_evidence={
            "present": artifact is not None,
            "source_report_id": (artifact or {}).get("report_id"),
            "claim_scope": (normalized or {}).get("claim_scope"),
            "runtime": (normalized or {}).get("methodology", {}).get("runtime"),
            "trace_count": traces,
            "minimum_trace_count": MIN_RUNTIME_TRACE_COUNT,
            "deployment_channel_count": channel_count,
            "minimum_deployment_channel_count": MIN_RUNTIME_CHANNEL_COUNT,
            "covered_path_count": covered_path_count,
            "required_path_ids": sorted(REQUIRED_RUNTIME_PATH_IDS),
            "path_ids": path_ids,
            "missing_required_path_ids": missing_path_ids,
            "validation_valid": (normalized or {}).get("validation", {}).get("valid"),
        },
        blocking_reason=None if ok else "missing live or mock-gateway runtime telemetry artifact",
    )


def _normalize_runtime_telemetry_artifact(
    artifact: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if artifact is None:
        return None
    if artifact.get("report_id") == "live_runtime_telemetry_v1":
        return artifact
    if (
        artifact.get("report_id") == "mock_runtime_telemetry_campaign_v1"
        and artifact.get("telemetry_report", {}).get("validation", {}).get("valid") is True
    ):
        return artifact["telemetry_report"]
    return artifact


def _list_count(artifact: dict[str, Any] | None, key: str) -> int:
    value = (artifact or {}).get(key)
    return len(value) if isinstance(value, list) else 0


def _requirement(
    *,
    requirement_id: str,
    status: str,
    required_evidence: str,
    observed_evidence: dict[str, Any],
    blocking_reason: str | None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "status": status,
        "required_evidence": required_evidence,
        "observed_evidence": observed_evidence,
        "blocking_reason": blocking_reason,
    }
