"""Scientific evidence bundle provenance contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.live_runtime_telemetry import run_mock_gateway_telemetry_campaign
from relic.eval.scientific_evidence_bundle import (
    build_scientific_evidence_bundle_from_file,
)


def test_scientific_evidence_bundle_hashes_and_validates_artifact_files(tmp_path):
    descriptor = _write_complete_descriptor(tmp_path)

    bundle = build_scientific_evidence_bundle_from_file(descriptor)

    assert bundle["report_id"] == "scientific_evidence_bundle_v1"
    assert bundle["claim_scope"] == "provenance_tracked_evidence_bundle"
    assert bundle["validation"]["valid"] is True
    assert bundle["summary"]["artifact_file_count"] == 6
    assert bundle["gate_report"]["overall_status"] == "satisfied"
    assert bundle["gate_report"]["summary"]["blocks_scientific_claims"] is False
    assert set(bundle["evidence_bundle"]) >= {
        "governance_benchmark",
        "live_model_generation_artifact",
        "human_annotation_results",
        "nonclinical_red_team_results",
        "longitudinal_pilot_results",
        "workbench_usability_results",
        "live_runtime_telemetry",
    }

    for artifact in bundle["artifact_manifest"]:
        assert artifact["sha256"].startswith("sha256:")
        assert artifact["size_bytes"] > 0
        assert artifact["loader_report_id"]


def test_scientific_evidence_bundle_rejects_descriptor_hash_mismatch(tmp_path):
    descriptor = _write_complete_descriptor(tmp_path, bad_hash=True)

    try:
        build_scientific_evidence_bundle_from_file(descriptor)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected bad artifact hash to be rejected")

    assert "sha256 mismatch" in message


def test_scientific_evidence_bundle_rejects_wrong_artifact_claim_scope(tmp_path):
    descriptor = _write_complete_descriptor(
        tmp_path,
        artifact_overrides={
            "live_model_generation_artifact": {
                "claim_scope": "unscoped_generation_records",
            },
        },
    )

    try:
        build_scientific_evidence_bundle_from_file(descriptor)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected wrong artifact claim_scope to be rejected")

    assert "live_model_generation_artifact claim_scope must be one of" in message


def test_eval_run_scientific_evidence_bundle_outputs_json(tmp_path, capsys):
    descriptor = _write_complete_descriptor(tmp_path)

    exit_code = eval_run.main(
        [
            "--experiment",
            "scientific_evidence_bundle",
            "--input",
            str(descriptor),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "scientific_evidence_bundle_v1"
    assert output["gate_report"]["overall_status"] == "satisfied"


def test_scientific_evidence_bundle_consumes_exported_mock_runtime_campaign(tmp_path):
    descriptor = _write_complete_descriptor(
        tmp_path,
        runtime_artifact=run_mock_gateway_telemetry_campaign(),
    )

    bundle = build_scientific_evidence_bundle_from_file(descriptor)

    telemetry = next(
        requirement
        for requirement in bundle["gate_report"]["requirements"]
        if requirement["requirement_id"] == "live_runtime_telemetry"
    )
    assert telemetry["status"] == "satisfied"
    assert telemetry["observed_evidence"]["source_report_id"] == "mock_runtime_telemetry_campaign_v1"


def _write_complete_descriptor(
    tmp_path,
    *,
    bad_hash: bool = False,
    runtime_artifact: dict | None = None,
    artifact_overrides: dict[str, dict] | None = None,
):
    artifacts = {
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
        "longitudinal_pilot_results": {
            "report_id": "longitudinal_pilot_results_v1",
            "claim_scope": "imported_nonclinical_pilot_results",
            "summary": {
                "participant_count": 12,
                "observed_duration_weeks": 2,
                "completion_rate": 1.0,
                "withdrawal_rate": 0.0,
                "workbench_task_success_rate": 0.95,
                "critical_error_count": 0,
                "system_event_total": 24,
            },
            "system_event_counts": {"audit_events_per_participant": 24},
            "workbench_task_results": [{}],
            "qualitative_summary": {"thematic_analysis_completed": True},
            "validation": {"valid": True},
        },
        "workbench_usability_results": {
            "report_id": "workbench_usability_results_v1",
            "claim_scope": "imported_workbench_usability_results",
            "summary": {
                "participant_count": 5,
                "task_result_count": 40,
                "task_success_rate": 0.95,
                "critical_error_rate": 0.0,
                "median_sus": 76,
                "median_raw_nasa_tlx": 38,
                "median_post_task_difficulty": 2,
            },
            "participant_summaries": [{} for _ in range(5)],
            "task_results": [{} for _ in range(40)],
            "qualitative_summary": {"thematic_analysis_completed": True},
            "thresholds": {"passed": True},
            "validation": {"valid": True},
        },
        "live_runtime_telemetry": runtime_artifact or {
            "report_id": "mock_runtime_telemetry_campaign_v1",
            "claim_scope": "mock_gateway_runtime_trace_campaign",
            "summary": {
                "trace_count": 3,
                "telemetry_validation_valid": True,
            },
            "telemetry_report": {
                "report_id": "live_runtime_telemetry_v1",
                "summary": {
                    "trace_count": 3,
                    "deployment_channel_count": 2,
                    "covered_path_count": 2,
                    "path_ids": [
                        "cron_delivery_path",
                        "hermes_entry_transform_hook",
                    ],
                },
                "claim_scope": "validated_runtime_trace_artifact",
                "methodology": {"runtime": "mock-gateway"},
                "validation": {"valid": True},
            },
            "validation": {"valid": True},
        },
    }
    for artifact_id, override in (artifact_overrides or {}).items():
        artifacts[artifact_id].update(override)

    descriptor_artifacts = {}
    for artifact_id, payload in artifacts.items():
        artifact_path = tmp_path / f"{artifact_id}.json"
        artifact_path.write_text(json.dumps(payload), encoding="utf-8")
        descriptor_artifacts[artifact_id] = {"path": artifact_path.name}

    if bad_hash:
        descriptor_artifacts["live_runtime_telemetry"]["sha256"] = f"sha256:{'0' * 64}"

    descriptor = tmp_path / "scientific-evidence-descriptor.json"
    descriptor.write_text(
        json.dumps(
            {
                "bundle_id": "fixture-complete-bundle",
                "artifacts": descriptor_artifacts,
            }
        ),
        encoding="utf-8",
    )
    return descriptor


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
