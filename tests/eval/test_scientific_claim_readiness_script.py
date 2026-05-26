"""Scientific claim-readiness workflow script contracts."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import scientific_claim_readiness


def test_scientific_claim_readiness_smoke_plan_records_expected_artifacts(tmp_path):
    plan = scientific_claim_readiness.build_plan(output_dir=tmp_path, mode="smoke")

    step_ids = [step.step_id for step in plan]
    assert step_ids == [
        "scientific_environment_manifest",
        "scientific_reproducibility_snapshot",
        "scientific_observation_remediation_audit",
        "mock_runtime_telemetry_campaign",
        "scientific_local_evidence_package",
        "scientific_defensibility_gate",
    ]
    artifacts = {step.step_id: step.artifact_path for step in plan}
    assert artifacts["scientific_environment_manifest"].name == "scientific-environment-manifest.json"
    assert artifacts["scientific_reproducibility_snapshot"].name == "scientific-reproducibility-snapshot.json"
    assert artifacts["scientific_observation_remediation_audit"].name == "scientific-observation-remediation-audit.json"
    assert artifacts["mock_runtime_telemetry_campaign"].name == "mock-runtime-telemetry-campaign.json"
    assert artifacts["scientific_local_evidence_package"].name == "scientific-local-evidence-package.json"
    assert artifacts["scientific_defensibility_gate"].name == "scientific-defensibility-gate.json"
    assert plan[-2].expected_nonzero is True
    assert plan[-1].expected_nonzero is True


def test_scientific_claim_readiness_full_plan_records_coverage_artifact(tmp_path):
    plan = scientific_claim_readiness.build_plan(output_dir=tmp_path, mode="full")

    steps = {step.step_id: step for step in plan}
    coverage_step = steps["broad_pytest_scientific_surface"]
    assert coverage_step.artifact_path == tmp_path / "scientific-surface-coverage.json"
    assert coverage_step.command[:4] == ("uv", "run", "--extra", "dev")
    assert "--cov=relic" in coverage_step.command
    assert f"--cov-report=json:{tmp_path / 'scientific-surface-coverage.json'}" in coverage_step.command


def test_scientific_claim_readiness_smoke_run_writes_blocked_report(tmp_path):
    exit_code = scientific_claim_readiness.main(
        ["--mode", "smoke", "--output-dir", str(tmp_path)]
    )

    report_path = tmp_path / "scientific-claim-readiness-run.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["report_id"] == "scientific_claim_readiness_run_v1"
    assert report["claim_scope"] == "local_claim_readiness_workflow_execution"
    assert report["overall_status"] == "blocked"
    assert report["summary"]["expected_block_count"] == 2
    assert report["summary"]["unexpected_failure_count"] == 0
    assert report["summary"]["artifact_file_count"] == 6

    steps = {step["step_id"]: step for step in report["steps"]}
    assert steps["scientific_local_evidence_package"]["status"] == "expected_block"
    assert steps["scientific_defensibility_gate"]["status"] == "expected_block"
    assert steps["scientific_defensibility_gate"]["exit_code"] == 1
    assert (tmp_path / "scientific-defensibility-gate.json").exists()
    assert (tmp_path / "scientific-observation-remediation-audit.json").exists()
    assert (tmp_path / "scientific-local-evidence-package.json").exists()
    assert (tmp_path / "logs" / "scientific_defensibility_gate.stdout").exists()


def test_shell_wrapper_delegates_to_python_runner():
    wrapper = Path("scripts/scientific_claim_readiness.sh").read_text(encoding="utf-8")

    assert "scripts/scientific_claim_readiness.py" in wrapper
    assert 'exec "$PYTHON"' in wrapper
