"""Runtime hook/adapter fault-injection drill contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.runtime_fault_injection import build_runtime_fault_injection_report


def test_runtime_fault_injection_report_exercises_fail_closed_paths():
    report = build_runtime_fault_injection_report()

    assert report["report_id"] == "runtime_fault_injection_v1"
    assert report["claim_scope"] == "synthetic_hook_adapter_fault_injection"
    assert report["summary"]["scenario_count"] >= 4
    assert report["summary"]["fail_closed_count"] == report["summary"]["scenario_count"]
    assert report["summary"]["unexpected_allow_count"] == 0
    assert report["summary"]["all_scenarios_passed"] is True
    assert report["validation"]["valid"] is True

    scenario_ids = {scenario["scenario_id"] for scenario in report["scenario_results"]}
    assert {
        "pre_llm_context_builder_exception",
        "pre_llm_fail_safe_already_triggered",
        "roleplay_l2_side_effect_without_approval",
        "hermes_entry_missing_subject_no_hook_registration",
    } <= scenario_ids


def test_eval_run_runtime_fault_injection_outputs_json(capsys):
    exit_code = eval_run.main(["--experiment", "runtime_fault_injection", "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "runtime_fault_injection_v1"
    assert output["validation"]["valid"] is True
