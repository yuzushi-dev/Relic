"""Longitudinal non-clinical pilot protocol packet.

This module prepares the Proposta 3 study design as machine-readable protocol.
It does not contain participant data or completed pilot results.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any


RESULTS_REPORT_ID = "longitudinal_pilot_results_v1"
RESULTS_CLAIM_SCOPE = "imported_nonclinical_pilot_results"
RAW_OR_CLINICAL_FIELD_NAMES = {
    "raw",
    "raw_notes",
    "raw_prompt",
    "raw_output",
    "clinical_outcome_measure",
    "diagnosis",
    "treatment_effect",
    "symptom_score",
}


def build_longitudinal_pilot_protocol() -> dict[str, Any]:
    """Build the non-clinical longitudinal pilot protocol."""
    return {
        "study_id": "longitudinal_nonclinical_pilot_v1",
        "claim_scope": "pilot_protocol_preparation",
        "duration_weeks": {"minimum": 2, "maximum": 4},
        "sample_size": {"minimum": 12, "maximum": 24},
        "positioning": {
            "non_clinical": True,
            "clinical_recruitment_allowed": False,
            "diagnosis_or_treatment_allowed": False,
            "crisis_support_allowed": False,
        },
        "research_questions": [
            "Do participants perceive continuity from subject-confirmed wording?",
            "Do participants understand remember/correct/forget/pause controls?",
            "Are follow-ups experienced as useful or intrusive?",
            "Do participants use correction, forget, or pause controls?",
            "Can researchers inspect markers, safety signals, delivery, and audit without panel confusion?",
            "Are tracker collapse, clinicalization, or backend disclosure observed during use?",
        ],
        "inclusion_criteria": [
            "adult participant",
            "explicit informed consent",
            "non-clinical use only",
            "willingness to use Gumi for defined pilot window",
            "willingness to complete brief surveys and final interview",
        ],
        "exclusion_criteria": [
            "clinical recruitment basis",
            "therapeutic or diagnostic use request",
            "crisis support seeking",
            "high-stakes medical legal or financial context",
        ],
        "consent_gates": [
            "memory_storage",
            "proactivity",
            "delivery",
            "researcher_review",
            "export_review",
            "withdrawal_and_deletion",
        ],
        "procedure": [
            "informed_consent",
            "memory_boundary_explanation",
            "initial_bootstrap",
            "bounded_free_use",
            "allowlisted_limited_followups",
            "correction_forget_pause_available",
            "weekly_brief_survey",
            "final_interview",
            "optional_export_review",
            "researcher_workbench_task_session",
        ],
        "participant_measures": {
            "weekly_likert": [
                "perceived_continuity",
                "perceived_intrusiveness",
                "control_over_memory",
                "trust_calibration",
                "proactivity_burden",
                "consent_clarity",
                "non_clinical_stance",
                "ease_of_correction",
                "willingness_to_continue",
                "discomfort_events",
            ],
            "final_interview_topics": [
                "remembered_well_moments",
                "remembered_too_much_moments",
                "tracker_like_moments",
                "clinical_framing_moments",
                "correction_forget_pause_moments",
                "backend_gumi_distinction",
            ],
            "validated_reference_instruments": [
                "SUS for workbench usability where applicable",
                "trust-in-automation item bank for trust calibration adaptation",
                "brief EMA-style burden item for repeated prompt burden",
            ],
        },
        "system_measures": [
            "markers_proposed",
            "markers_confirmed",
            "markers_corrected",
            "markers_forgotten",
            "pause_resume_events",
            "followups_due",
            "followups_delivered",
            "no_reply_decisions",
            "blocked_delivery",
            "output_transformations",
            "backend_disclosure_attempts",
            "clinicalization_blocks",
            "safety_signal_events",
            "audit_events_per_participant",
        ],
        "researcher_workbench_tasks": [
            {
                "task_id": "find_confirmed_marker",
                "prompt": "Find a specified subject-confirmed marker and report its source state.",
                "success_metric": "marker_found_with_correct_status",
                "timing_metric": "seconds_to_completion",
            },
            {
                "task_id": "reconstruct_followup_decision",
                "prompt": "Reconstruct why a follow-up was delivered or blocked.",
                "success_metric": "correct_delivery_or_block_reason",
                "timing_metric": "seconds_to_completion",
            },
            {
                "task_id": "distinguish_safety_from_continuity",
                "prompt": "Classify records as researcher-facing safety signal or Gumi-facing continuity.",
                "success_metric": "classification_accuracy",
                "timing_metric": "seconds_to_completion",
            },
            {
                "task_id": "generate_redacted_export",
                "prompt": "Locate and generate the redacted export artifact for one subject.",
                "success_metric": "export_generated_without_raw_private_content",
                "timing_metric": "seconds_to_completion",
            },
            {
                "task_id": "interpret_audit_log",
                "prompt": "Use Chronicle/Workbench evidence to explain one correction or forget event.",
                "success_metric": "correct_event_chain_explanation",
                "timing_metric": "seconds_to_completion",
            },
        ],
        "analysis_plan": {
            "primary_mode": "descriptive_feasibility",
            "quantitative_outputs": [
                "weekly_descriptive_trends",
                "event_count_rates",
                "completion_rate",
                "withdrawal_rate",
                "workbench_task_completion_time",
                "workbench_task_error_rate",
            ],
            "qualitative_outputs": [
                "thematic_analysis",
                "failure_case_analysis",
                "correction_forget_pause_episodes",
            ],
            "comparative_extension": "optional_small_comparative_design",
        },
        "risk_controls": [
            "non-clinical onboarding language",
            "crisis and therapeutic-use exclusion",
            "delivery allowlist and quiet hours",
            "participant pause/forget/delete controls",
            "researcher-facing safety signals not injected as Gumi memory",
        ],
        "claim_limitations": [
            "no diagnosis or treatment measurement",
            "participant outcome results not collected",
            "small sample feasibility only",
            "short duration and novelty effects expected",
            "not evidence of longitudinal deployment safety until executed and analyzed",
        ],
        "literature_basis": [
            "feasibility and acceptability pilot design",
            "System Usability Scale for researcher workbench usability",
            "trust-in-automation measurement for trust calibration",
            "EMA and micro-EMA burden guidance for repeated prompts",
        ],
    }


def build_longitudinal_pilot_results_report_from_file(path: Path) -> dict[str, Any]:
    """Load caller-supplied pilot results JSON and validate it."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return build_longitudinal_pilot_results_report(
        protocol=payload["protocol"],
        observed_duration_weeks=payload["observed_duration_weeks"],
        participant_records=payload["participant_records"],
        system_event_counts=payload["system_event_counts"],
        workbench_task_results=payload["workbench_task_results"],
        qualitative_summary=payload["qualitative_summary"],
    )


def build_longitudinal_pilot_results_report(
    *,
    protocol: dict[str, Any],
    observed_duration_weeks: int | float,
    participant_records: list[dict[str, Any]],
    system_event_counts: dict[str, int],
    workbench_task_results: list[dict[str, Any]],
    qualitative_summary: dict[str, Any],
) -> dict[str, Any]:
    """Validate and summarize imported non-clinical longitudinal pilot results."""
    errors = _validate_pilot_results(
        protocol=protocol,
        observed_duration_weeks=observed_duration_weeks,
        participant_records=participant_records,
        system_event_counts=system_event_counts,
        workbench_task_results=workbench_task_results,
        qualitative_summary=qualitative_summary,
    )
    if errors:
        raise ValueError("; ".join(errors))

    completed = [
        record
        for record in participant_records
        if record["final_interview_completed"] and not record["withdrawn"]
    ]
    withdrawal_count = sum(1 for record in participant_records if record["withdrawn"])
    attempted_tasks = sum(int(task["attempted"]) for task in workbench_task_results)
    succeeded_tasks = sum(int(task["succeeded"]) for task in workbench_task_results)
    critical_errors = sum(int(task["critical_errors"]) for task in workbench_task_results)

    return {
        "report_id": RESULTS_REPORT_ID,
        "claim_scope": RESULTS_CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "imported_nonclinical_longitudinal_pilot_results",
            "study_id": protocol["study_id"],
            "source_claim_scope": protocol["claim_scope"],
            "analysis_mode": protocol["analysis_plan"]["primary_mode"],
        },
        "summary": {
            "participant_count": len(participant_records),
            "observed_duration_weeks": observed_duration_weeks,
            "completion_rate": len(completed) / len(participant_records),
            "withdrawal_rate": withdrawal_count / len(participant_records),
            "workbench_task_success_rate": (
                succeeded_tasks / attempted_tasks if attempted_tasks else 0.0
            ),
            "critical_error_count": critical_errors,
            "system_event_total": sum(system_event_counts.values()),
        },
        "participant_measure_summary": _summarize_weekly_surveys(
            protocol,
            participant_records,
        ),
        "system_event_counts": dict(system_event_counts),
        "workbench_task_results": [dict(task) for task in workbench_task_results],
        "qualitative_summary": dict(qualitative_summary),
        "validation": {
            "valid": True,
            "checked_rules": [
                "nonclinical_protocol_scope",
                "sample_size_12_to_24",
                "duration_2_to_4_weeks",
                "all_consent_gates_present",
                "weekly_surveys_cover_observed_duration",
                "required_system_measures_present",
                "required_workbench_tasks_present",
                "no_raw_or_clinical_outcome_fields",
            ],
        },
        "claim_limitations": [
            "caller-supplied pilot results only",
            "descriptive feasibility evidence, not causal efficacy evidence",
            "no diagnosis, treatment, crisis-support, or clinical outcome claim",
            "short-duration pilot remains vulnerable to novelty effects",
        ],
    }


def _summarize_weekly_surveys(
    protocol: dict[str, Any],
    participant_records: list[dict[str, Any]],
) -> dict[str, float]:
    measures = protocol["participant_measures"]["weekly_likert"]
    return {
        measure: mean(
            int(survey[measure])
            for record in participant_records
            for survey in record["weekly_surveys"]
        )
        for measure in measures
    }


def _validate_pilot_results(
    *,
    protocol: dict[str, Any],
    observed_duration_weeks: int | float,
    participant_records: list[dict[str, Any]],
    system_event_counts: dict[str, int],
    workbench_task_results: list[dict[str, Any]],
    qualitative_summary: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    errors.extend(_prohibited_field_errors(protocol, "protocol"))
    errors.extend(_prohibited_field_errors(participant_records, "participant_records"))
    errors.extend(_prohibited_field_errors(system_event_counts, "system_event_counts"))
    errors.extend(_prohibited_field_errors(workbench_task_results, "workbench_task_results"))
    errors.extend(_prohibited_field_errors(qualitative_summary, "qualitative_summary"))

    if protocol.get("study_id") != "longitudinal_nonclinical_pilot_v1":
        errors.append("protocol.study_id must be longitudinal_nonclinical_pilot_v1")
    if protocol.get("claim_scope") != "pilot_protocol_preparation":
        errors.append("protocol.claim_scope must be pilot_protocol_preparation")
    if protocol.get("positioning", {}).get("non_clinical") is not True:
        errors.append("protocol must be explicitly non-clinical")

    if observed_duration_weeks < 2 or observed_duration_weeks > 4:
        errors.append("observed duration must be between 2 and 4 weeks")
    participant_count = len(participant_records)
    if participant_count < 12 or participant_count > 24:
        errors.append("participant_count must be between 12 and 24")

    consent_gates = set(protocol.get("consent_gates", []))
    weekly_measures = set(protocol.get("participant_measures", {}).get("weekly_likert", []))
    participant_ids: set[str] = set()
    for index, record in enumerate(participant_records):
        prefix = f"participant_records[{index}]"
        required_fields = {
            "participant_id",
            "consent_gates",
            "weekly_surveys",
            "final_interview_completed",
            "withdrawn",
        }
        missing = sorted(required_fields - set(record))
        if missing:
            errors.append(f"{prefix} missing fields: {missing}")
            continue
        participant_id = str(record["participant_id"])
        if participant_id in participant_ids:
            errors.append(f"{prefix} duplicate participant_id")
        participant_ids.add(participant_id)
        if set(record["consent_gates"]) != consent_gates:
            errors.append(f"{prefix} consent_gates must match protocol gates")
        if len(record["weekly_surveys"]) < int(observed_duration_weeks):
            errors.append(f"{prefix} weekly_surveys do not cover observed duration")
        for survey_index, survey in enumerate(record["weekly_surveys"]):
            survey_prefix = f"{prefix}.weekly_surveys[{survey_index}]"
            missing_measures = sorted(weekly_measures - set(survey))
            if missing_measures:
                errors.append(f"{survey_prefix} missing measures: {missing_measures}")
            for measure in weekly_measures.intersection(survey):
                value = survey[measure]
                if not isinstance(value, int) or value < 1 or value > 5:
                    errors.append(f"{survey_prefix}.{measure} must be integer 1-5")

    required_system_measures = set(protocol.get("system_measures", []))
    missing_system_measures = sorted(required_system_measures - set(system_event_counts))
    if missing_system_measures:
        errors.append(f"system_event_counts missing measures: {missing_system_measures}")
    for measure, value in system_event_counts.items():
        if measure not in required_system_measures:
            errors.append(f"system_event_counts unknown measure: {measure}")
        if not isinstance(value, int) or value < 0:
            errors.append(f"system_event_counts.{measure} must be a non-negative integer")

    required_task_ids = {
        task["task_id"] for task in protocol.get("researcher_workbench_tasks", [])
    }
    observed_task_ids = {
        task.get("task_id") for task in workbench_task_results
    }
    missing_tasks = sorted(required_task_ids - observed_task_ids)
    if missing_tasks:
        errors.append(f"workbench_task_results missing tasks: {missing_tasks}")
    for index, task in enumerate(workbench_task_results):
        prefix = f"workbench_task_results[{index}]"
        required_fields = {"task_id", "attempted", "succeeded", "critical_errors", "median_seconds"}
        missing = sorted(required_fields - set(task))
        if missing:
            errors.append(f"{prefix} missing fields: {missing}")
            continue
        if task["task_id"] not in required_task_ids:
            errors.append(f"{prefix} unknown task_id")
        attempted = int(task["attempted"])
        succeeded = int(task["succeeded"])
        if attempted <= 0:
            errors.append(f"{prefix}.attempted must be positive")
        if succeeded < 0 or succeeded > attempted:
            errors.append(f"{prefix}.succeeded must be between 0 and attempted")
        if int(task["critical_errors"]) < 0:
            errors.append(f"{prefix}.critical_errors must be non-negative")
        if float(task["median_seconds"]) < 0:
            errors.append(f"{prefix}.median_seconds must be non-negative")

    if qualitative_summary.get("thematic_analysis_completed") is not True:
        errors.append("qualitative_summary.thematic_analysis_completed must be true")

    return errors


def _prohibited_field_errors(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in RAW_OR_CLINICAL_FIELD_NAMES:
                errors.append(f"{child_path} is prohibited in non-clinical pilot results")
            errors.extend(_prohibited_field_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_prohibited_field_errors(child, f"{path}[{index}]"))
    return errors
