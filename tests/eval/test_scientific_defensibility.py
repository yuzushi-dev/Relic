"""Scientific defensibility gate contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.controlled_benchmark import run_governance_benchmark
from relic.eval.live_runtime_telemetry import run_mock_gateway_telemetry_campaign
from relic.eval.scientific_defensibility import build_scientific_defensibility_report


def test_scientific_defensibility_gate_blocks_without_external_evidence():
    report = build_scientific_defensibility_report()

    assert report["report_id"] == "scientific_defensibility_gate_v1"
    assert report["claim_scope"] == "claim_readiness_evidence_gate"
    assert report["overall_status"] == "blocked"
    assert report["summary"]["blocks_scientific_claims"] is True

    blocked_ids = {
        requirement["requirement_id"]
        for requirement in report["requirements"]
        if requirement["status"] == "blocked"
    }
    assert blocked_ids >= {
        "live_model_generation_campaign",
        "human_annotation_results",
        "nonclinical_expert_red_team",
        "longitudinal_pilot_results",
        "workbench_usability_results",
        "live_runtime_telemetry",
    }

    benchmark = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "controlled_governance_benchmark"
    )
    assert benchmark["status"] == "satisfied"


def test_scientific_defensibility_gate_accepts_valid_external_artifact_shapes():
    benchmark = run_governance_benchmark()
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "governance_benchmark": benchmark,
            "live_model_generation_artifact": {
                "report_id": "live_model_generation_artifact_v1",
                "claim_scope": "redacted_external_generation_records",
                "summary": {
                    "provider_count": 2,
                    "completed_generation_count": 400,
                    "expected_generation_count": 400,
                    "completeness_rate": 1.0,
                    "reproducibility_metadata_complete": True,
                },
                "provider_manifest": [{}, {}],
                "generation_records": [{} for _ in range(400)],
                "validation": {"valid": True},
            },
            "human_annotation_results": {
                "report_id": "human_annotation_results_v1",
                "claim_scope": "imported_human_annotation_results",
                "summary": {
                    "item_count": 240,
                    "annotation_count": 720,
                    "complete_item_count": 240,
                    "annotator_count": 3,
                    "minimum_annotators_per_item": 3,
                },
                "source_packet": {"item_count": 240},
                "annotation_records": [{} for _ in range(720)],
                "reliability": _high_annotation_reliability(),
                "validation": {"valid": True},
            },
            "nonclinical_red_team_results": {
                "report_id": "nonclinical_red_team_results_v1",
                "claim_scope": "imported_expert_red_team_results",
                "summary": {
                    "case_count": 120,
                    "reviewer_count": 2,
                    "risk_category_count": 6,
                    "unsafe_case_count": 100,
                    "unsafe_allow_rate": 0.0,
                    "reviewer_agreement_rate": 0.95,
                },
                "reviewer_manifest": [{}, {}],
                "case_results": [{} for _ in range(120)],
                "validation": {"valid": True},
            },
        }
    )

    statuses = {
        requirement["requirement_id"]: requirement["status"]
        for requirement in report["requirements"]
    }
    assert statuses["live_model_generation_campaign"] == "satisfied"
    assert statuses["human_annotation_results"] == "satisfied"
    assert statuses["nonclinical_expert_red_team"] == "satisfied"
    assert statuses["longitudinal_pilot_results"] == "blocked"
    assert report["overall_status"] == "blocked"


def test_scientific_defensibility_gate_blocks_low_human_annotation_reliability():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "human_annotation_results": {
                "report_id": "human_annotation_results_v1",
                "claim_scope": "imported_human_annotation_results",
                "summary": {
                    "item_count": 240,
                    "complete_item_count": 240,
                    "annotator_count": 3,
                    "minimum_annotators_per_item": 3,
                },
                "reliability": {
                    "binary_by_label": {
                        label: {
                            "percent_agreement": 0.95,
                            "krippendorff_alpha_nominal": 0.45,
                        }
                        for label in [
                            "clinicalization_present",
                            "backend_disclosure_present",
                            "tracker_collapse_present",
                            "dependency_reinforcement_present",
                            "false_lived_experience_present",
                            "unconfirmed_recall_present",
                            "inappropriate_advice_present",
                        ]
                    },
                    "likert_by_dimension": {
                        dimension: {"icc_2k": 0.52}
                        for dimension in [
                            "continuity",
                            "subject_word_fidelity",
                            "non_clinical_stance",
                            "boundary_preservation",
                            "non_intrusiveness",
                            "non_tracker_behavior",
                            "diegetic_consistency",
                            "helpfulness_within_boundary",
                            "correction_respect",
                            "burden_sensitivity",
                        ]
                    },
                },
                "validation": {"valid": True},
            },
        }
    )

    annotation = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "human_annotation_results"
    )
    assert annotation["status"] == "blocked"
    assert annotation["observed_evidence"]["minimum_binary_krippendorff_alpha_nominal"] == 0.45
    assert annotation["observed_evidence"]["minimum_likert_icc_2k"] == 0.52


def test_scientific_defensibility_gate_blocks_live_generation_without_reproducibility_metadata():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "live_model_generation_artifact": {
                "report_id": "live_model_generation_artifact_v1",
                "claim_scope": "redacted_external_generation_records",
                "summary": {
                    "provider_count": 2,
                    "completed_generation_count": 400,
                    "expected_generation_count": 400,
                    "completeness_rate": 1.0,
                    "reproducibility_metadata_complete": False,
                },
                "validation": {"valid": True},
            },
        }
    )

    live_generation = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "live_model_generation_campaign"
    )
    assert live_generation["status"] == "blocked"
    assert live_generation["observed_evidence"]["reproducibility_metadata_complete"] is False


def test_scientific_defensibility_gate_blocks_summary_only_live_generation_artifact():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "live_model_generation_artifact": {
                "report_id": "live_model_generation_artifact_v1",
                "claim_scope": "redacted_external_generation_records",
                "summary": {
                    "provider_count": 2,
                    "completed_generation_count": 400,
                    "expected_generation_count": 400,
                    "completeness_rate": 1.0,
                    "reproducibility_metadata_complete": True,
                },
                "validation": {"valid": True},
            },
        }
    )

    live_generation = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "live_model_generation_campaign"
    )
    assert live_generation["status"] == "blocked"
    assert live_generation["observed_evidence"]["generation_record_count"] == 0
    assert live_generation["observed_evidence"]["provider_manifest_count"] == 0


def test_scientific_defensibility_gate_blocks_red_team_without_risk_category_coverage():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "nonclinical_red_team_results": {
                "report_id": "nonclinical_red_team_results_v1",
                "claim_scope": "imported_expert_red_team_results",
                "summary": {
                    "case_count": 120,
                    "reviewer_count": 2,
                    "risk_category_count": 1,
                    "unsafe_case_count": 120,
                    "unsafe_allow_rate": 0.0,
                    "reviewer_agreement_rate": 0.95,
                },
                "validation": {"valid": True},
            },
        }
    )

    red_team = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "nonclinical_expert_red_team"
    )
    assert red_team["status"] == "blocked"
    assert red_team["observed_evidence"]["risk_category_count"] == 1


def test_eval_run_scientific_defensibility_gate_outputs_blocking_json(capsys):
    exit_code = eval_run.main(["--experiment", "scientific_defensibility_gate", "--json"])

    assert exit_code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "scientific_defensibility_gate_v1"
    assert output["summary"]["blocks_scientific_claims"] is True


def test_scientific_defensibility_gate_requires_imported_result_claim_scopes():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "longitudinal_pilot_results": {
                "report_id": "longitudinal_pilot_results_v1",
                "summary": {
                    "participant_count": 12,
                    "observed_duration_weeks": 2,
                },
                "validation": {"valid": True},
            },
            "workbench_usability_results": {
                "report_id": "workbench_usability_results_v1",
                "summary": {
                    "participant_count": 5,
                    "critical_error_rate": 0.0,
                },
                "validation": {"valid": True},
            },
        }
    )

    statuses = {
        requirement["requirement_id"]: requirement
        for requirement in report["requirements"]
    }
    assert statuses["longitudinal_pilot_results"]["status"] == "blocked"
    assert statuses["workbench_usability_results"]["status"] == "blocked"
    assert statuses["longitudinal_pilot_results"]["observed_evidence"]["claim_scope"] is None
    assert statuses["workbench_usability_results"]["observed_evidence"]["claim_scope"] is None


def test_scientific_defensibility_gate_blocks_weak_longitudinal_feasibility_results():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "longitudinal_pilot_results": {
                "report_id": "longitudinal_pilot_results_v1",
                "claim_scope": "imported_nonclinical_pilot_results",
                "summary": {
                    "participant_count": 12,
                    "observed_duration_weeks": 2,
                    "completion_rate": 0.5,
                    "withdrawal_rate": 0.5,
                    "workbench_task_success_rate": 0.6,
                    "critical_error_count": 1,
                    "system_event_total": 24,
                },
                "validation": {"valid": True},
            },
        }
    )

    pilot = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "longitudinal_pilot_results"
    )
    assert pilot["status"] == "blocked"
    assert pilot["observed_evidence"]["completion_rate"] == 0.5
    assert pilot["observed_evidence"]["critical_error_count"] == 1


def test_scientific_defensibility_gate_blocks_weak_workbench_usability_results():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "workbench_usability_results": {
                "report_id": "workbench_usability_results_v1",
                "claim_scope": "imported_workbench_usability_results",
                "summary": {
                    "participant_count": 5,
                    "task_success_rate": 0.5,
                    "critical_error_rate": 0.0,
                    "median_sus": 76,
                    "median_raw_nasa_tlx": 38,
                    "median_post_task_difficulty": 2,
                },
                "thresholds": {"passed": False},
                "validation": {"valid": True},
            },
        }
    )

    workbench = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "workbench_usability_results"
    )
    assert workbench["status"] == "blocked"
    assert workbench["observed_evidence"]["task_success_rate"] == 0.5
    assert workbench["observed_evidence"]["thresholds_passed"] is False


def test_scientific_defensibility_gate_accepts_mock_runtime_campaign_for_telemetry():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "live_runtime_telemetry": run_mock_gateway_telemetry_campaign(),
        }
    )

    telemetry = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "live_runtime_telemetry"
    )
    assert telemetry["status"] == "satisfied"
    assert telemetry["observed_evidence"]["runtime"] == "mock-gateway"


def test_scientific_defensibility_gate_blocks_runtime_telemetry_without_required_paths():
    report = build_scientific_defensibility_report(
        evidence_bundle={
            "live_runtime_telemetry": {
                "report_id": "live_runtime_telemetry_v1",
                "claim_scope": "validated_runtime_trace_artifact",
                "methodology": {"runtime": "mock-gateway"},
                "summary": {
                    "trace_count": 3,
                    "deployment_channel_count": 2,
                    "covered_path_count": 1,
                    "path_ids": ["hermes_entry_transform_hook"],
                },
                "validation": {"valid": True},
            },
        }
    )

    telemetry = next(
        requirement
        for requirement in report["requirements"]
        if requirement["requirement_id"] == "live_runtime_telemetry"
    )
    assert telemetry["status"] == "blocked"
    assert telemetry["observed_evidence"]["covered_path_count"] == 1
    assert telemetry["observed_evidence"]["missing_required_path_ids"] == [
        "cron_delivery_path"
    ]


def _high_annotation_reliability():
    return {
        "binary_by_label": {
            label: {
                "percent_agreement": 0.95,
                "krippendorff_alpha_nominal": 0.82,
            }
            for label in [
                "clinicalization_present",
                "backend_disclosure_present",
                "tracker_collapse_present",
                "dependency_reinforcement_present",
                "false_lived_experience_present",
                "unconfirmed_recall_present",
                "inappropriate_advice_present",
            ]
        },
        "likert_by_dimension": {
            dimension: {"icc_2k": 0.81}
            for dimension in [
                "continuity",
                "subject_word_fidelity",
                "non_clinical_stance",
                "boundary_preservation",
                "non_intrusiveness",
                "non_tracker_behavior",
                "diegetic_consistency",
                "helpfulness_within_boundary",
                "correction_respect",
                "burden_sensitivity",
            ]
        },
    }
