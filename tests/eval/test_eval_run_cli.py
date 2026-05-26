"""Tests for scripts/eval_run.py CLI contract."""

from __future__ import annotations

import json

from scripts import eval_run


def test_eval_run_module_gumi_roleplay_outputs_nonzero_scenarios(capsys):
    """The documented --module gumi_roleplay flag runs real fixtures."""
    exit_code = eval_run.main(["--module", "gumi_roleplay", "--json"])

    assert exit_code in (0, 1)
    output = json.loads(capsys.readouterr().out)
    assert output["total_scenarios"] > 0
    assert "prompt_context_completeness" in output["gate_results"]


def test_eval_run_default_outputs_nonzero_scenarios(capsys):
    """Default eval invocation exercises at least one fixture-backed suite."""
    exit_code = eval_run.main(["--json"])

    assert exit_code in (0, 1)
    output = json.loads(capsys.readouterr().out)
    assert output["total_scenarios"] > 0


def test_eval_run_governance_benchmark_writes_output_file_without_json(tmp_path, capsys):
    """Artifact-producing experiments can write descriptor-ready JSON files."""
    output_path = tmp_path / "governance-benchmark.json"

    exit_code = eval_run.main(
        [
            "--experiment",
            "governance_benchmark",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "Experiment: governance_failure_mode_benchmark_v1" in stdout
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["experiment_id"] == "governance_failure_mode_benchmark_v1"
    assert output["claim_scope"] == "synthetic_fixture_controlled"


def test_eval_run_default_release_gate_writes_output_file_with_json(tmp_path, capsys):
    output_path = tmp_path / "release-gate.json"

    exit_code = eval_run.main(["--json", "--output", str(output_path)])

    assert exit_code in (0, 1)
    stdout = json.loads(capsys.readouterr().out)
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["total_scenarios"] == stdout["total_scenarios"]
    assert output["gate_results"] == stdout["gate_results"]
