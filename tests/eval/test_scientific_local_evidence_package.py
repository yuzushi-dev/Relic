"""Local scientific evidence package contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.scientific_local_evidence_package import (
    build_scientific_local_evidence_package,
)


def test_scientific_local_evidence_package_satisfies_only_local_requirements():
    package = build_scientific_local_evidence_package()

    assert package["report_id"] == "scientific_local_evidence_package_v1"
    assert package["claim_scope"] == "local_synthetic_evidence_package"
    assert package["validation"]["valid"] is True
    assert package["summary"]["local_evidence_artifact_count"] == 2
    assert package["summary"]["gate_satisfied_count"] == 2
    assert package["summary"]["gate_blocked_count"] == 5
    assert package["summary"]["blocks_scientific_claims"] is True

    requirements = {
        row["requirement_id"]: row["status"]
        for row in package["gate_report"]["requirements"]
    }
    assert requirements["controlled_governance_benchmark"] == "satisfied"
    assert requirements["live_runtime_telemetry"] == "satisfied"
    assert requirements["live_model_generation_campaign"] == "blocked"
    assert requirements["human_annotation_results"] == "blocked"
    assert requirements["nonclinical_expert_red_team"] == "blocked"
    assert requirements["longitudinal_pilot_results"] == "blocked"
    assert requirements["workbench_usability_results"] == "blocked"


def test_eval_run_scientific_local_evidence_package_outputs_json(tmp_path, capsys):
    output_path = tmp_path / "scientific-local-evidence-package.json"

    exit_code = eval_run.main(
        [
            "--experiment",
            "scientific_local_evidence_package",
            "--output",
            str(output_path),
            "--json",
        ]
    )

    assert exit_code == 1
    stdout = json.loads(capsys.readouterr().out)
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout["report_id"] == "scientific_local_evidence_package_v1"
    assert output["summary"] == stdout["summary"]
