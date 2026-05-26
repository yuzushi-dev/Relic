"""Researcher Workbench usability task-study protocol tests."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.workbench_usability import (
    build_workbench_usability_protocol,
    build_workbench_usability_results_report,
)


def test_workbench_usability_protocol_has_scoped_claim_and_literature_measures():
    protocol = build_workbench_usability_protocol()

    assert protocol["study_id"] == "researcher_workbench_usability_v1"
    assert protocol["claim_scope"] == "usability_protocol_preparation"
    assert protocol["participant_role"] == "researcher_or_auditor"
    assert protocol["sample_size"]["minimum"] >= 5
    assert protocol["sample_size"]["recommended"] >= protocol["sample_size"]["minimum"]
    assert set(protocol["measurement_instruments"]) >= {
        "task_success",
        "time_on_task_seconds",
        "critical_error_count",
        "noncritical_error_count",
        "post_task_difficulty_likert_1_7",
        "system_usability_scale",
        "raw_nasa_tlx",
        "think_aloud_notes",
    }
    assert "no completed researcher data" in " ".join(protocol["limitations"])


def test_workbench_usability_tasks_cover_observation_packet_requirements():
    protocol = build_workbench_usability_protocol()
    tasks = {task["task_id"]: task for task in protocol["tasks"]}

    assert set(tasks) >= {
        "WB01_find_confirmed_marker",
        "WB02_reconstruct_followup_decision",
        "WB03_distinguish_safety_from_continuity",
        "WB04_generate_redacted_export",
        "WB05_interpret_audit_timeline",
        "WB06_apply_correction_and_trace_propagation",
        "WB07_check_subject_scoping_and_pause",
        "WB08_identify_boundary_overreach",
    }
    for task in tasks.values():
        assert task["research_question"]
        assert task["success_criteria"]
        assert task["primary_metrics"]
        assert task["fixture_evidence"]
        assert task["code_evidence"]
        assert task["test_evidence"]


def test_workbench_usability_protocol_declares_analysis_plan_and_stopping_rules():
    protocol = build_workbench_usability_protocol()

    analysis = protocol["analysis_plan"]
    assert analysis["quantitative_outputs"] >= [
        "task_success_rate_by_task",
        "median_time_on_task_by_task",
        "critical_error_rate_by_task",
    ]
    assert "thematic_analysis_of_think_aloud_notes" in analysis["qualitative_outputs"]
    assert protocol["success_thresholds"]["critical_error_rate_max"] <= 0.1
    assert protocol["success_thresholds"]["median_sus_min"] >= 68
    assert protocol["stopping_rules"]


def test_workbench_usability_protocol_keeps_current_evidence_separate_from_future_results():
    protocol = build_workbench_usability_protocol()

    assert protocol["current_evidence"]["fixture_backed"] is True
    assert protocol["current_evidence"]["completed_user_study"] is False
    assert protocol["current_evidence"]["live_workbench_backend_complete"] is False
    assert protocol["result_schema"]["per_task_result_fields"] >= [
        "task_id",
        "participant_id",
        "success",
        "time_on_task_seconds",
        "critical_errors",
    ]


def test_eval_run_workbench_usability_protocol_outputs_json(capsys):
    exit_code = eval_run.main(["--experiment", "workbench_usability_protocol", "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["study_id"] == "researcher_workbench_usability_v1"
    assert output["claim_scope"] == "usability_protocol_preparation"
    assert len(output["tasks"]) >= 8


def test_workbench_usability_results_validate_task_study_thresholds():
    protocol = build_workbench_usability_protocol()
    report = build_workbench_usability_results_report(
        protocol=protocol,
        participant_summaries=_participant_summaries(5),
        task_results=_task_results(protocol, participant_count=5),
        qualitative_summary={
            "thematic_analysis_completed": True,
            "critical_error_root_cause_count": 0,
            "recommended_panel_or_label_changes": 2,
        },
    )

    assert report["report_id"] == "workbench_usability_results_v1"
    assert report["claim_scope"] == "imported_workbench_usability_results"
    assert report["validation"]["valid"] is True
    assert report["summary"]["participant_count"] == 5
    assert report["summary"]["critical_error_rate"] == 0.0
    assert report["summary"]["median_sus"] >= 68
    assert report["thresholds"]["passed"] is True


def test_workbench_usability_results_reject_raw_or_incomplete_records():
    protocol = build_workbench_usability_protocol()

    try:
        build_workbench_usability_results_report(
            protocol=protocol,
            participant_summaries=[
                {
                    "participant_id": "r-001",
                    "role": "researcher",
                    "prior_relic_experience": "some",
                    "system_usability_scale": 70,
                    "raw_nasa_tlx": 40,
                    "debrief_themes": ["clear"],
                    "raw_notes": "unredacted notes",
                }
            ],
            task_results=[],
            qualitative_summary={"thematic_analysis_completed": False},
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected invalid Workbench results to be rejected")

    assert "raw_notes" in message
    assert "participant_count" in message
    assert "missing task results" in message


def test_eval_run_workbench_usability_results_imports_json(tmp_path, capsys):
    protocol = build_workbench_usability_protocol()
    artifact_path = tmp_path / "workbench-results.json"
    artifact_path.write_text(
        json.dumps(
            {
                "protocol": protocol,
                "participant_summaries": _participant_summaries(5),
                "task_results": _task_results(protocol, participant_count=5),
                "qualitative_summary": {
                    "thematic_analysis_completed": True,
                    "critical_error_root_cause_count": 0,
                    "recommended_panel_or_label_changes": 2,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = eval_run.main(
        [
            "--experiment",
            "workbench_usability_results",
            "--input",
            str(artifact_path),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "workbench_usability_results_v1"
    assert output["validation"]["valid"] is True


def _participant_summaries(count: int) -> list[dict]:
    return [
        {
            "participant_id": f"r-{index + 1:03d}",
            "role": "researcher",
            "prior_relic_experience": "some",
            "system_usability_scale": 76,
            "raw_nasa_tlx": 38,
            "debrief_themes": ["clear labels", "audit path visible"],
        }
        for index in range(count)
    ]


def _task_results(protocol: dict, *, participant_count: int) -> list[dict]:
    rows = []
    for participant_index in range(participant_count):
        participant_id = f"r-{participant_index + 1:03d}"
        for task in protocol["tasks"]:
            rows.append(
                {
                    "task_id": task["task_id"],
                    "participant_id": participant_id,
                    "success": True,
                    "time_on_task_seconds": 45,
                    "critical_errors": 0,
                    "noncritical_errors": 1,
                    "post_task_difficulty_likert_1_7": 2,
                    "notes_redacted": "Found the relevant panel.",
                }
            )
    return rows
