"""Scientific observation remediation audit contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.scientific_observation_remediation_audit import (
    build_scientific_observation_remediation_audit,
)


def test_scientific_observation_remediation_audit_maps_gaps_to_current_evidence():
    audit = build_scientific_observation_remediation_audit()

    assert audit["report_id"] == "scientific_observation_remediation_audit_v1"
    assert audit["claim_scope"] == "observation_gap_to_evidence_traceability"
    assert audit["source_documents"] == [
        "docs/relic_gumi_scientific_observations/02_matrice_claim_evidenze.md",
        "docs/relic_gumi_scientific_observations/03_lacune_scientifiche_e_validita.md",
        "docs/relic_gumi_scientific_observations/04_proposte_sperimentali.md",
    ]
    assert audit["validation"]["valid"] is True

    summary = audit["summary"]
    assert summary["gap_count"] >= 12
    assert summary["resolved_or_partially_resolved_count"] > 0
    assert summary["blocked_external_evidence_count"] >= 5
    assert summary["broad_scientific_claims_ready"] is False

    gaps = {gap["gap_id"]: gap for gap in audit["gaps"]}
    assert gaps["runtime_path_coverage"]["status"] in {"partially_resolved", "locally_resolved"}
    assert "runtime_path_coverage_v1" in gaps["runtime_path_coverage"]["current_evidence"]
    assert gaps["single_evaluation_script"]["status"] == "locally_resolved"
    assert "scientific_claim_readiness_run_v1" in gaps["single_evaluation_script"]["current_evidence"]
    assert gaps["docker_reproducible_environment"]["status"] == "locally_resolved"
    assert "scientific_environment_manifest_v1" in gaps["docker_reproducible_environment"]["current_evidence"]
    assert gaps["live_model_generation"]["status"] == "blocked_external_evidence"
    assert gaps["human_annotation_results"]["status"] == "blocked_external_evidence"
    assert gaps["workbench_usability_results"]["status"] == "blocked_external_evidence"


def test_eval_run_scientific_observation_remediation_audit_outputs_json(tmp_path, capsys):
    output_path = tmp_path / "scientific-observation-remediation-audit.json"

    exit_code = eval_run.main(
        [
            "--experiment",
            "scientific_observation_remediation_audit",
            "--output",
            str(output_path),
            "--json",
        ]
    )

    assert exit_code == 0
    stdout = json.loads(capsys.readouterr().out)
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout["report_id"] == "scientific_observation_remediation_audit_v1"
    assert output["summary"] == stdout["summary"]
