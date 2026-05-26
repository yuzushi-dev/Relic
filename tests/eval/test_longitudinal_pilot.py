"""Longitudinal non-clinical pilot protocol contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.longitudinal_pilot import (
    build_longitudinal_pilot_protocol,
    build_longitudinal_pilot_results_report,
)


def test_longitudinal_pilot_protocol_matches_proposal_three_bounds():
    """Pilot protocol keeps Proposta 3 scope, duration, sample, and non-clinical boundary."""
    protocol = build_longitudinal_pilot_protocol()

    assert protocol["study_id"] == "longitudinal_nonclinical_pilot_v1"
    assert protocol["claim_scope"] == "pilot_protocol_preparation"
    assert protocol["duration_weeks"] == {"minimum": 2, "maximum": 4}
    assert protocol["sample_size"] == {"minimum": 12, "maximum": 24}
    assert protocol["positioning"]["non_clinical"] is True
    assert "no diagnosis or treatment measurement" in protocol["claim_limitations"]
    assert "participant outcome results not collected" in protocol["claim_limitations"]


def test_longitudinal_pilot_has_inclusion_exclusion_and_consent_gates():
    """Protocol encodes eligibility and explicit consent instead of relying on prose."""
    protocol = build_longitudinal_pilot_protocol()

    assert set(protocol["inclusion_criteria"]) >= {
        "adult participant",
        "explicit informed consent",
        "non-clinical use only",
        "willingness to use Gumi for defined pilot window",
        "willingness to complete brief surveys and final interview",
    }
    assert set(protocol["exclusion_criteria"]) >= {
        "clinical recruitment basis",
        "therapeutic or diagnostic use request",
        "crisis support seeking",
        "high-stakes medical legal or financial context",
    }
    assert set(protocol["consent_gates"]) >= {
        "memory_storage",
        "proactivity",
        "delivery",
        "researcher_review",
        "export_review",
        "withdrawal_and_deletion",
    }


def test_longitudinal_pilot_measures_subject_system_and_researcher_outcomes():
    """Protocol includes participant measures, system event counts, and workbench tasks."""
    protocol = build_longitudinal_pilot_protocol()

    assert set(protocol["participant_measures"]["weekly_likert"]) >= {
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
    }
    assert set(protocol["system_measures"]) >= {
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
    }
    assert len(protocol["researcher_workbench_tasks"]) >= 5
    assert all("success_metric" in task for task in protocol["researcher_workbench_tasks"])


def test_longitudinal_pilot_analysis_plan_is_descriptive_and_feasibility_scoped():
    """Analysis plan avoids causal/clinical overclaiming and covers feasibility outputs."""
    protocol = build_longitudinal_pilot_protocol()

    assert protocol["analysis_plan"]["primary_mode"] == "descriptive_feasibility"
    assert set(protocol["analysis_plan"]["quantitative_outputs"]) >= {
        "weekly_descriptive_trends",
        "event_count_rates",
        "completion_rate",
        "withdrawal_rate",
        "workbench_task_completion_time",
        "workbench_task_error_rate",
    }
    assert set(protocol["analysis_plan"]["qualitative_outputs"]) >= {
        "thematic_analysis",
        "failure_case_analysis",
        "correction_forget_pause_episodes",
    }
    assert protocol["analysis_plan"]["comparative_extension"] == "optional_small_comparative_design"


def test_eval_run_longitudinal_protocol_outputs_packet(capsys):
    """CLI emits the pilot protocol as protocol preparation, not participant evidence."""
    exit_code = eval_run.main(["--experiment", "longitudinal_pilot_protocol", "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["study_id"] == "longitudinal_nonclinical_pilot_v1"
    assert output["claim_scope"] == "pilot_protocol_preparation"
    assert output["positioning"]["non_clinical"] is True


def test_longitudinal_pilot_results_validate_nonclinical_completion():
    protocol = build_longitudinal_pilot_protocol()
    report = build_longitudinal_pilot_results_report(
        protocol=protocol,
        observed_duration_weeks=2,
        participant_records=_participant_records(12, protocol),
        system_event_counts={measure: 1 for measure in protocol["system_measures"]},
        workbench_task_results=[
            {
                "task_id": task["task_id"],
                "attempted": 12,
                "succeeded": 11,
                "critical_errors": 0,
                "median_seconds": 42,
            }
            for task in protocol["researcher_workbench_tasks"]
        ],
        qualitative_summary={
            "thematic_analysis_completed": True,
            "failure_case_count": 2,
            "correction_forget_pause_episode_count": 3,
        },
    )

    assert report["report_id"] == "longitudinal_pilot_results_v1"
    assert report["claim_scope"] == "imported_nonclinical_pilot_results"
    assert report["validation"]["valid"] is True
    assert report["summary"]["participant_count"] == 12
    assert report["summary"]["observed_duration_weeks"] == 2
    assert report["summary"]["completion_rate"] == 1.0
    assert report["summary"]["critical_error_count"] == 0


def test_longitudinal_pilot_results_reject_clinical_or_raw_fields():
    protocol = build_longitudinal_pilot_protocol()

    try:
        build_longitudinal_pilot_results_report(
            protocol=protocol,
            observed_duration_weeks=1,
            participant_records=[
                {
                    "participant_id": "p-001",
                    "consent_gates": protocol["consent_gates"],
                    "weekly_surveys": [],
                    "final_interview_completed": False,
                    "withdrawn": False,
                    "clinical_outcome_measure": "not allowed",
                    "raw_notes": "unredacted notes",
                }
            ],
            system_event_counts={},
            workbench_task_results=[],
            qualitative_summary={"thematic_analysis_completed": False},
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected invalid pilot results to be rejected")

    assert "clinical_outcome_measure" in message
    assert "raw_notes" in message
    assert "duration" in message
    assert "participant_count" in message


def test_eval_run_longitudinal_results_imports_json(tmp_path, capsys):
    protocol = build_longitudinal_pilot_protocol()
    artifact_path = tmp_path / "pilot-results.json"
    artifact_path.write_text(
        json.dumps(
            {
                "protocol": protocol,
                "observed_duration_weeks": 2,
                "participant_records": _participant_records(12, protocol),
                "system_event_counts": {
                    measure: 1 for measure in protocol["system_measures"]
                },
                "workbench_task_results": [
                    {
                        "task_id": task["task_id"],
                        "attempted": 12,
                        "succeeded": 11,
                        "critical_errors": 0,
                        "median_seconds": 42,
                    }
                    for task in protocol["researcher_workbench_tasks"]
                ],
                "qualitative_summary": {
                    "thematic_analysis_completed": True,
                    "failure_case_count": 2,
                    "correction_forget_pause_episode_count": 3,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = eval_run.main(
        [
            "--experiment",
            "longitudinal_pilot_results",
            "--input",
            str(artifact_path),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "longitudinal_pilot_results_v1"
    assert output["validation"]["valid"] is True


def _participant_records(count: int, protocol: dict) -> list[dict]:
    return [
        {
            "participant_id": f"p-{index + 1:03d}",
            "consent_gates": list(protocol["consent_gates"]),
            "weekly_surveys": [
                {
                    "week": 1,
                    **{
                        measure: 4
                        for measure in protocol["participant_measures"]["weekly_likert"]
                    },
                },
                {
                    "week": 2,
                    **{
                        measure: 4
                        for measure in protocol["participant_measures"]["weekly_likert"]
                    },
                },
            ],
            "final_interview_completed": True,
            "withdrawn": False,
        }
        for index in range(count)
    ]
