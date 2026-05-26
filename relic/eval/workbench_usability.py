"""Researcher Workbench usability task-study protocol.

This module prepares a measurable study protocol. It does not contain completed
researcher observations, SUS scores, workload scores, or task results.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any


RESULTS_REPORT_ID = "workbench_usability_results_v1"
RESULTS_CLAIM_SCOPE = "imported_workbench_usability_results"
PROHIBITED_FIELD_NAMES = {
    "raw",
    "raw_notes",
    "raw_prompt",
    "raw_output",
    "raw_export",
    "clinical_label",
    "diagnosis",
    "treatment_recommendation",
}


def _task(
    *,
    task_id: str,
    title: str,
    research_question: str,
    scenario: str,
    success_criteria: list[str],
    primary_metrics: list[str],
    fixture_evidence: list[str],
    code_evidence: list[str],
    test_evidence: list[str],
    critical_errors: list[str],
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "title": title,
        "research_question": research_question,
        "scenario": scenario,
        "success_criteria": success_criteria,
        "primary_metrics": primary_metrics,
        "fixture_evidence": fixture_evidence,
        "code_evidence": code_evidence,
        "test_evidence": test_evidence,
        "critical_errors": critical_errors,
    }


def _tasks() -> list[dict[str, Any]]:
    return [
        _task(
            task_id="WB01_find_confirmed_marker",
            title="Find a subject-confirmed continuity marker",
            research_question="Can a researcher find what Gumi is allowed to remember without confusing it with broad memory or safety data?",
            scenario="Given subject subj_001, locate a confirmed Shared Continuity marker and identify its subject words, correction status, TTL, and recall eligibility.",
            success_criteria=[
                "Participant identifies the correct marker row or fixture item.",
                "Participant reports subject words without inventing clinical labels.",
                "Participant reports whether the marker is eligible for recall.",
            ],
            primary_metrics=[
                "task_success",
                "time_on_task_seconds",
                "critical_error_count",
                "post_task_difficulty_likert_1_7",
            ],
            fixture_evidence=[
                "fixtures/researcher-workbench/gumi_instance_subj_001.json",
                "fixtures/ui/shared_continuity_row.json",
            ],
            code_evidence=[
                "relic/ui/workbench_panels.py",
                "relic/ui/view_models.py",
            ],
            test_evidence=[
                "tests/ui/test_shared_continuity_panel_contract.py",
                "tests/ui/test_subject_overview_contract.py",
            ],
            critical_errors=[
                "Treats an unconfirmed or safety-derived item as a continuity marker.",
                "Reports a clinical label as Gumi-facing memory.",
            ],
        ),
        _task(
            task_id="WB02_reconstruct_followup_decision",
            title="Reconstruct why a follow-up was delivered or blocked",
            research_question="Can a researcher reconstruct a proactive delivery decision from cron, delivery, and audit surfaces?",
            scenario="Given a follow-up or cron decision, explain whether Gumi should deliver, stay silent, or block, and cite the decisive evidence.",
            success_criteria=[
                "Participant identifies the decision outcome.",
                "Participant names at least one reason code or gate input.",
                "Participant does not infer delivery from candidate generation alone.",
            ],
            primary_metrics=[
                "task_success",
                "time_on_task_seconds",
                "critical_error_count",
                "noncritical_error_count",
            ],
            fixture_evidence=[
                "fixtures/researcher-workbench/cron_console_subj_001.json",
                "fixtures/researcher-workbench/event_stream_subj_001.json",
            ],
            code_evidence=[
                "relic/gumi_plugin/cron_wiring.py",
                "relic/hermes_runtime.py",
                "relic/ui/workbench_panels.py",
            ],
            test_evidence=[
                "tests/ui/test_cron_decision_point_console_contract.py",
                "tests/ui/test_cron_decision_point_status_visible.py",
                "tests/gumi_plugin/test_decision_log_canonical.py",
            ],
            critical_errors=[
                "Confuses CANDIDATE with DELIVER.",
                "Ignores quiet-hours, allowlist, pause, or delivery-state evidence.",
            ],
        ),
        _task(
            task_id="WB03_distinguish_safety_from_continuity",
            title="Distinguish Safety Signals from Shared Continuity",
            research_question="Can a researcher inspect safety governance without turning signals into continuity memory?",
            scenario="Given a safety signal row and a continuity row, decide which data Gumi may see and which data remains researcher-facing only.",
            success_criteria=[
                "Participant correctly identifies safety signals as researcher-facing.",
                "Participant correctly identifies continuity marker visibility and recall constraints.",
                "Participant does not create or recommend a continuity marker from a safety signal.",
            ],
            primary_metrics=[
                "task_success",
                "critical_error_count",
                "post_task_difficulty_likert_1_7",
                "think_aloud_notes",
            ],
            fixture_evidence=[
                "fixtures/ui/safety_signal_row.json",
                "fixtures/ui/shared_continuity_row.json",
            ],
            code_evidence=[
                "relic/ui/workbench_panels.py",
                "relic/patterns/runtime_pack_sanitizer.py",
            ],
            test_evidence=[
                "tests/ui/test_safety_signals_panel_contract.py",
                "tests/ui/test_shared_continuity_panel_contract.py",
                "tests/gumi_continuity/test_sensitive_signal_not_stored_as_continuity_marker.py",
            ],
            critical_errors=[
                "Marks a safety signal as Gumi-facing continuity.",
                "Uses a clinical or diagnostic label as behavior memory.",
            ],
        ),
        _task(
            task_id="WB04_generate_redacted_export",
            title="Generate or verify a redacted export",
            research_question="Can a researcher produce an audit/export bundle without exposing raw data unintentionally?",
            scenario="Given export controls and a subject, identify the redacted export path and verify what should be included or excluded.",
            success_criteria=[
                "Participant selects redacted export behavior.",
                "Participant identifies safety-signal export constraints.",
                "Participant can find or interpret export manifest counts.",
            ],
            primary_metrics=[
                "task_success",
                "time_on_task_seconds",
                "critical_error_count",
                "system_usability_scale",
            ],
            fixture_evidence=[
                "fixtures/researcher-workbench/export_manifest_subj_001.json",
            ],
            code_evidence=[
                "relic/ui/permissions.py",
                "relic/chronicle/cli/main.py",
            ],
            test_evidence=[
                "tests/ui/test_export_replication_console_contract.py",
                "tests/ui/test_export_redaction_required.py",
                "tests/chronicle/test_access_audit.py",
            ],
            critical_errors=[
                "Chooses raw export when redacted export is required.",
                "Assumes researcher-facing safety signals are subject-facing export content.",
            ],
        ),
        _task(
            task_id="WB05_interpret_audit_timeline",
            title="Interpret an audit timeline",
            research_question="Can a researcher reconstruct event order and source modules from the audit timeline?",
            scenario="Given an event stream, reconstruct the sequence from message or cron event through decision and output state.",
            success_criteria=[
                "Participant orders events correctly.",
                "Participant identifies at least two source modules or actor scopes.",
                "Participant cites a trace, event, or timestamp rather than relying on prose memory.",
            ],
            primary_metrics=[
                "task_success",
                "time_on_task_seconds",
                "noncritical_error_count",
                "raw_nasa_tlx",
            ],
            fixture_evidence=[
                "fixtures/researcher-workbench/event_stream_subj_001.json",
            ],
            code_evidence=[
                "relic/chronicle/reader.py",
                "relic/ui/workbench_panels.py",
            ],
            test_evidence=[
                "tests/ui/test_timeline_event_stream_contract.py",
                "tests/chronicle/test_reader.py",
                "tests/eval/test_chronicle_audit_coverage.py",
            ],
            critical_errors=[
                "Misattributes a system-generated event as subject evidence.",
                "Omits a blocking or correction event that changes interpretation.",
            ],
        ),
        _task(
            task_id="WB06_apply_correction_and_trace_propagation",
            title="Apply a correction and trace propagation",
            research_question="Can a researcher correct an artifact through the allowed feedback path and understand when it affects runtime?",
            scenario="Given a disputed item, submit or inspect a correction and identify feedback propagation stages.",
            success_criteria=[
                "Participant uses feedback/correction path rather than direct artifact write.",
                "Participant identifies that runtime changes require compiler/replay propagation.",
                "Participant can find the feedback trace or correction queue item.",
            ],
            primary_metrics=[
                "task_success",
                "time_on_task_seconds",
                "critical_error_count",
                "think_aloud_notes",
            ],
            fixture_evidence=[
                "fixtures/researcher-workbench/corrections_queue_subj_001.json",
                "fixtures/ui-validation/expected_researcher_feedback_trace.jsonl",
            ],
            code_evidence=[
                "relic/ui/feedback.py",
                "relic/ui/replay.py",
                "relic/ui/api.py",
            ],
            test_evidence=[
                "tests/ui/test_corrections_queue_contract.py",
                "tests/ui/test_feedback_event.py",
                "tests/ui/test_no_direct_artifact_write.py",
                "tests/ui/test_replication_bundle_feedback_trace.py",
            ],
            critical_errors=[
                "Attempts direct artifact mutation.",
                "Assumes feedback immediately changes runtime before compiler/replay propagation.",
            ],
        ),
        _task(
            task_id="WB07_check_subject_scoping_and_pause",
            title="Check subject scoping and pause state",
            research_question="Can a researcher verify that pause/proactivity and Gumi instance state are subject-scoped?",
            scenario="Given two subjects, identify each subject's Gumi instance and whether proactivity pause applies only to the selected subject.",
            success_criteria=[
                "Participant identifies subject-scoped Gumi instances.",
                "Participant does not apply pause state globally across subjects.",
                "Participant identifies redacted cross-subject aggregate constraints.",
            ],
            primary_metrics=[
                "task_success",
                "critical_error_count",
                "noncritical_error_count",
                "post_task_difficulty_likert_1_7",
            ],
            fixture_evidence=[
                "fixtures/researcher-workbench/test_fixture_two_subjects.json",
                "fixtures/researcher-workbench/cross_subject_aggregate.json",
            ],
            code_evidence=[
                "relic/ui/permissions.py",
                "relic/ui/view_models.py",
            ],
            test_evidence=[
                "tests/ui/test_no_global_gumi_runtime.py",
                "tests/ui/test_subject_scoped_gumi_instance.py",
                "tests/ui/test_pause_proactive_is_subject_scoped.py",
                "tests/ui/test_cross_subject_view_redacted_by_default.py",
            ],
            critical_errors=[
                "Treats Gumi as a global singleton.",
                "Leaks raw cross-subject content from aggregate views.",
            ],
        ),
        _task(
            task_id="WB08_identify_boundary_overreach",
            title="Identify boundary overreach",
            research_question="Can a researcher spot relational, clinical, tracker, or dependency overreach from boundary-risk surfaces?",
            scenario="Given a boundary risk panel, identify the overreach indicators and the available careful-distancing control.",
            success_criteria=[
                "Participant identifies at least one boundary risk indicator.",
                "Participant selects careful distancing or review rather than clinical labeling.",
                "Participant distinguishes relational boundary risk from safety-signal memory.",
            ],
            primary_metrics=[
                "task_success",
                "critical_error_count",
                "raw_nasa_tlx",
                "think_aloud_notes",
            ],
            fixture_evidence=[
                "fixtures/researcher-workbench/boundary_risk_subj_001.json",
            ],
            code_evidence=[
                "relic/ui/workbench_panels.py",
                "relic/ui/contracts.py",
            ],
            test_evidence=[
                "tests/ui/test_boundary_risk_monitor_contract.py",
                "tests/ui/test_boundary_monitor_shows_overreach.py",
                "tests/ui/test_careful_distancing_control_available.py",
            ],
            critical_errors=[
                "Converts boundary overreach into a diagnostic label.",
                "Misses an explicit overreach indicator that should trigger review.",
            ],
        ),
    ]


def build_workbench_usability_protocol() -> dict[str, Any]:
    """Build the Workbench researcher usability protocol."""
    return {
        "study_id": "researcher_workbench_usability_v1",
        "claim_scope": "usability_protocol_preparation",
        "participant_role": "researcher_or_auditor",
        "sample_size": {
            "minimum": 5,
            "recommended": 8,
            "maximum": 12,
            "rationale": "Small formative usability sample focused on task breakdown and failure discovery, not population inference.",
        },
        "measurement_instruments": [
            "task_success",
            "time_on_task_seconds",
            "critical_error_count",
            "noncritical_error_count",
            "post_task_difficulty_likert_1_7",
            "system_usability_scale",
            "raw_nasa_tlx",
            "think_aloud_notes",
        ],
        "procedure": [
            "Screen for researchers, auditors, or study operators familiar with non-clinical human-subject research.",
            "Give a 5-10 minute orientation to Workbench panels and the non-clinical boundary vocabulary.",
            "Run one practice task that is not scored.",
            "Counterbalance task order across participants.",
            "Use think-aloud notes for qualitative issue discovery; record time separately from verbal pauses when possible.",
            "Collect post-task difficulty after each task.",
            "Collect SUS and raw NASA-TLX after the task set.",
            "Debrief confusion points and classify critical errors.",
        ],
        "tasks": _tasks(),
        "success_thresholds": {
            "task_success_rate_min": 0.8,
            "critical_error_rate_max": 0.1,
            "median_sus_min": 68,
            "median_post_task_difficulty_max": 3,
            "median_raw_nasa_tlx_max": 50,
        },
        "analysis_plan": {
            "quantitative_outputs": [
                "task_success_rate_by_task",
                "median_time_on_task_by_task",
                "critical_error_rate_by_task",
                "noncritical_error_rate_by_task",
                "median_post_task_difficulty_by_task",
                "median_sus",
                "median_raw_nasa_tlx",
            ],
            "qualitative_outputs": [
                "thematic_analysis_of_think_aloud_notes",
                "confusion_points_by_panel",
                "critical_error_root_cause_table",
                "recommended_panel_or_label_changes",
            ],
            "reporting_rules": [
                "Report descriptive statistics only unless the study is powered for comparison.",
                "Do not treat SUS or NASA-TLX as evidence of safety effectiveness.",
                "Separate usability failures from runtime governance failures.",
            ],
        },
        "stopping_rules": [
            "Stop and revise protocol if two participants misinterpret safety signals as continuity memory.",
            "Stop and revise UI labels if any participant selects raw export when redacted export is required.",
            "Stop and revise task instructions if more than one participant cannot locate the relevant fixture surface.",
        ],
        "result_schema": {
            "per_task_result_fields": [
                "task_id",
                "participant_id",
                "success",
                "time_on_task_seconds",
                "critical_errors",
                "noncritical_errors",
                "post_task_difficulty_likert_1_7",
                "notes_redacted",
            ],
            "study_result_fields": [
                "participant_id",
                "role",
                "prior_relic_experience",
                "system_usability_scale",
                "raw_nasa_tlx",
                "debrief_themes",
            ],
        },
        "current_evidence": {
            "fixture_backed": True,
            "completed_user_study": False,
            "live_workbench_backend_complete": False,
            "evidence_sources": [
                "fixtures/researcher-workbench/",
                "fixtures/ui-validation/",
                "relic/ui/",
                "tests/ui/",
            ],
        },
        "limitations": [
            "This contains no completed researcher data.",
            "This does not prove Workbench usability, only protocol readiness.",
            "The current OSS Workbench backend is fixture-backed/read-only for several surfaces.",
            "Task success in this protocol would not prove clinical safety or participant benefit.",
        ],
        "next_required_evidence": [
            "Run the protocol with researchers or auditors and publish anonymized task results.",
            "Record task success, time, critical errors, SUS, raw NASA-TLX, and qualitative themes.",
            "Use findings to revise panel labels, fixture coverage, and Workbench task flows.",
        ],
    }


def build_workbench_usability_results_report_from_file(path: Path) -> dict[str, Any]:
    """Load caller-supplied Workbench usability results JSON and validate it."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return build_workbench_usability_results_report(
        protocol=payload["protocol"],
        participant_summaries=payload["participant_summaries"],
        task_results=payload["task_results"],
        qualitative_summary=payload["qualitative_summary"],
    )


def build_workbench_usability_results_report(
    *,
    protocol: dict[str, Any],
    participant_summaries: list[dict[str, Any]],
    task_results: list[dict[str, Any]],
    qualitative_summary: dict[str, Any],
) -> dict[str, Any]:
    """Validate and summarize imported researcher Workbench usability results."""
    errors = _validate_workbench_results(
        protocol=protocol,
        participant_summaries=participant_summaries,
        task_results=task_results,
        qualitative_summary=qualitative_summary,
    )
    if errors:
        raise ValueError("; ".join(errors))

    task_success_rate = sum(1 for row in task_results if row["success"]) / len(task_results)
    critical_error_count = sum(int(row["critical_errors"]) for row in task_results)
    critical_error_rate = critical_error_count / len(task_results)
    median_difficulty = median(
        int(row["post_task_difficulty_likert_1_7"]) for row in task_results
    )
    median_sus = median(
        int(row["system_usability_scale"]) for row in participant_summaries
    )
    median_tlx = median(int(row["raw_nasa_tlx"]) for row in participant_summaries)
    thresholds = protocol["success_thresholds"]
    thresholds_passed = (
        task_success_rate >= thresholds["task_success_rate_min"]
        and critical_error_rate <= thresholds["critical_error_rate_max"]
        and median_sus >= thresholds["median_sus_min"]
        and median_difficulty <= thresholds["median_post_task_difficulty_max"]
        and median_tlx <= thresholds["median_raw_nasa_tlx_max"]
    )

    return {
        "report_id": RESULTS_REPORT_ID,
        "claim_scope": RESULTS_CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "imported_researcher_workbench_usability_results",
            "study_id": protocol["study_id"],
            "source_claim_scope": protocol["claim_scope"],
            "participant_role": protocol["participant_role"],
        },
        "summary": {
            "participant_count": len(participant_summaries),
            "task_result_count": len(task_results),
            "task_success_rate": task_success_rate,
            "critical_error_count": critical_error_count,
            "critical_error_rate": critical_error_rate,
            "median_sus": median_sus,
            "median_raw_nasa_tlx": median_tlx,
            "median_post_task_difficulty": median_difficulty,
        },
        "thresholds": {
            "configured": thresholds,
            "passed": thresholds_passed,
        },
        "task_metrics": _task_metrics(protocol, task_results),
        "participant_summaries": [dict(row) for row in participant_summaries],
        "task_results": [dict(row) for row in task_results],
        "qualitative_summary": dict(qualitative_summary),
        "validation": {
            "valid": True,
            "checked_rules": [
                "protocol_scope",
                "sample_size_bounds",
                "participant_summary_fields",
                "one_result_per_participant_task",
                "valid_task_metric_ranges",
                "qualitative_summary_completed",
                "no_raw_or_clinical_fields",
            ],
        },
        "claim_limitations": [
            "caller-supplied usability results only",
            "formative researcher/auditor usability evidence, not participant outcome evidence",
            "SUS and NASA-TLX do not prove runtime safety or clinical benefit",
            "task success does not prove production Workbench backend completeness",
        ],
    }


def _task_metrics(protocol: dict[str, Any], task_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = []
    for task in protocol["tasks"]:
        rows = [row for row in task_results if row["task_id"] == task["task_id"]]
        metrics.append(
            {
                "task_id": task["task_id"],
                "attempted": len(rows),
                "success_rate": sum(1 for row in rows if row["success"]) / len(rows),
                "critical_error_rate": sum(int(row["critical_errors"]) for row in rows)
                / len(rows),
                "median_time_on_task_seconds": median(
                    float(row["time_on_task_seconds"]) for row in rows
                ),
            }
        )
    return metrics


def _validate_workbench_results(
    *,
    protocol: dict[str, Any],
    participant_summaries: list[dict[str, Any]],
    task_results: list[dict[str, Any]],
    qualitative_summary: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    errors.extend(_prohibited_field_errors(protocol, "protocol"))
    errors.extend(_prohibited_field_errors(participant_summaries, "participant_summaries"))
    errors.extend(_prohibited_field_errors(task_results, "task_results"))
    errors.extend(_prohibited_field_errors(qualitative_summary, "qualitative_summary"))

    if protocol.get("study_id") != "researcher_workbench_usability_v1":
        errors.append("protocol.study_id must be researcher_workbench_usability_v1")
    if protocol.get("claim_scope") != "usability_protocol_preparation":
        errors.append("protocol.claim_scope must be usability_protocol_preparation")

    sample_size = protocol.get("sample_size", {})
    participant_count = len(participant_summaries)
    if participant_count < int(sample_size.get("minimum", 5)) or participant_count > int(
        sample_size.get("maximum", 12)
    ):
        errors.append("participant_count outside protocol sample_size bounds")

    participant_ids: set[str] = set()
    for index, row in enumerate(participant_summaries):
        prefix = f"participant_summaries[{index}]"
        required = {
            "participant_id",
            "role",
            "prior_relic_experience",
            "system_usability_scale",
            "raw_nasa_tlx",
            "debrief_themes",
        }
        missing = sorted(required - set(row))
        if missing:
            errors.append(f"{prefix} missing fields: {missing}")
            continue
        participant_id = str(row["participant_id"])
        if participant_id in participant_ids:
            errors.append(f"{prefix} duplicate participant_id")
        participant_ids.add(participant_id)
        if int(row["system_usability_scale"]) < 0 or int(row["system_usability_scale"]) > 100:
            errors.append(f"{prefix}.system_usability_scale must be 0-100")
        if int(row["raw_nasa_tlx"]) < 0 or int(row["raw_nasa_tlx"]) > 100:
            errors.append(f"{prefix}.raw_nasa_tlx must be 0-100")
        if not isinstance(row["debrief_themes"], list):
            errors.append(f"{prefix}.debrief_themes must be a list")

    task_ids = {task["task_id"] for task in protocol.get("tasks", [])}
    seen_task_results: set[tuple[str, str]] = set()
    for index, row in enumerate(task_results):
        prefix = f"task_results[{index}]"
        required = {
            "task_id",
            "participant_id",
            "success",
            "time_on_task_seconds",
            "critical_errors",
            "noncritical_errors",
            "post_task_difficulty_likert_1_7",
            "notes_redacted",
        }
        missing = sorted(required - set(row))
        if missing:
            errors.append(f"{prefix} missing fields: {missing}")
            continue
        if row["task_id"] not in task_ids:
            errors.append(f"{prefix} unknown task_id")
        if row["participant_id"] not in participant_ids:
            errors.append(f"{prefix} participant_id not in participant_summaries")
        result_key = (str(row["participant_id"]), str(row["task_id"]))
        if result_key in seen_task_results:
            errors.append(f"{prefix} duplicate participant/task result")
        seen_task_results.add(result_key)
        if not isinstance(row["success"], bool):
            errors.append(f"{prefix}.success must be boolean")
        if float(row["time_on_task_seconds"]) < 0:
            errors.append(f"{prefix}.time_on_task_seconds must be non-negative")
        if int(row["critical_errors"]) < 0:
            errors.append(f"{prefix}.critical_errors must be non-negative")
        if int(row["noncritical_errors"]) < 0:
            errors.append(f"{prefix}.noncritical_errors must be non-negative")
        difficulty = int(row["post_task_difficulty_likert_1_7"])
        if difficulty < 1 or difficulty > 7:
            errors.append(f"{prefix}.post_task_difficulty_likert_1_7 must be 1-7")

    expected_results = {
        (participant_id, task_id)
        for participant_id in participant_ids
        for task_id in task_ids
    }
    missing_results = expected_results - seen_task_results
    if missing_results:
        errors.append(f"missing task results for participant/task pairs: {len(missing_results)}")

    if qualitative_summary.get("thematic_analysis_completed") is not True:
        errors.append("qualitative_summary.thematic_analysis_completed must be true")

    return errors


def _prohibited_field_errors(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in PROHIBITED_FIELD_NAMES:
                errors.append(f"{child_path} is prohibited in Workbench usability results")
            errors.extend(_prohibited_field_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_prohibited_field_errors(child, f"{path}[{index}]"))
    return errors
