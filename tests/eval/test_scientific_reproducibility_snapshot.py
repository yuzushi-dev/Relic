"""Local reproducibility snapshot contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.scientific_reproducibility_snapshot import (
    build_scientific_reproducibility_snapshot,
)


def test_scientific_reproducibility_snapshot_hashes_local_reports():
    snapshot = build_scientific_reproducibility_snapshot()

    assert snapshot["report_id"] == "scientific_reproducibility_snapshot_v1"
    assert snapshot["claim_scope"] == "reproducible_local_evaluation_snapshot"
    assert snapshot["summary"]["local_report_count"] >= 8
    assert snapshot["summary"]["external_evidence_artifacts_included"] == 0
    assert snapshot["validation"]["valid"] is True
    assert "does not create missing external evidence" in snapshot["claim_limitations"]

    report_ids = {entry["report_id"] for entry in snapshot["report_manifest"]}
    assert "governance_failure_mode_benchmark_v1" in report_ids
    assert "mock_runtime_telemetry_campaign_v1" in report_ids
    assert "multi_subject_isolation_load_v1" in report_ids
    assert "runtime_fault_injection_v1" in report_ids
    assert "construct_operationalization_v1" in report_ids
    assert "scientific_environment_manifest_v1" in report_ids
    assert "scientific_observation_remediation_audit_v1" in report_ids
    assert "scientific_local_evidence_package_v1" in report_ids
    assert "scientific_defensibility_gate_v1" in report_ids
    for entry in snapshot["report_manifest"]:
        assert entry["sha256"].startswith("sha256:")
        assert entry["reproduce_command"].startswith(
            "python scripts/eval_run.py --experiment "
        )
        assert "--output" in entry["reproduce_command"]


def test_eval_run_scientific_reproducibility_snapshot_outputs_json(tmp_path, capsys):
    output_path = tmp_path / "scientific-reproducibility-snapshot.json"

    exit_code = eval_run.main(
        [
            "--experiment",
            "scientific_reproducibility_snapshot",
            "--output",
            str(output_path),
            "--json",
        ]
    )

    assert exit_code == 0
    stdout = json.loads(capsys.readouterr().out)
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout["report_id"] == "scientific_reproducibility_snapshot_v1"
    assert output["report_manifest"] == stdout["report_manifest"]
