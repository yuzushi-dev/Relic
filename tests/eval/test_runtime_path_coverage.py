"""Runtime path coverage report contract tests."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.runtime_path_coverage import build_runtime_path_coverage_report


def test_runtime_path_coverage_report_has_claims_evidence_and_limitations():
    report = build_runtime_path_coverage_report()

    assert report["report_id"] == "runtime_path_coverage_v1"
    assert report["claim_scope"] == "static_contract_inventory"
    assert report["methodology"]["evidence_model"] == "claims_arguments_evidence"
    assert "not live Hermes deployment telemetry" in " ".join(report["limitations"])
    assert report["summary"]["total_paths"] >= 8
    assert report["summary"]["covered_paths"] >= 3
    assert report["summary"]["partial_paths"] >= 1
    assert report["summary"]["compatibility_surface_paths"] >= 1
    assert report["summary"]["unresolved_paths"] >= 1


def test_runtime_path_coverage_declares_required_runtime_invariants():
    report = build_runtime_path_coverage_report()

    invariant_ids = {item["invariant_id"] for item in report["runtime_invariants"]}
    assert invariant_ids >= {
        "subject_scope",
        "context_admission",
        "output_review",
        "delivery_gate",
        "durable_continuity",
        "pause_forget_resume",
        "resume_reconciliation",
        "chronicle_audit",
        "safety_signal_isolation",
    }
    for invariant in report["runtime_invariants"]:
        assert invariant["claim"]
        assert invariant["required_evidence"]
        assert invariant["failure_if_missing"]


def test_runtime_path_coverage_entries_are_traceable_to_code_and_tests():
    report = build_runtime_path_coverage_report()

    entries = report["path_inventory"]
    path_ids = {entry["path_id"] for entry in entries}
    assert path_ids >= {
        "hermes_plugin_pcp_injection",
        "standalone_shared_continuity_adapter_hook",
        "standalone_shared_continuity_legacy_hook",
        "hermes_entry_transform_hook",
        "no_agent_cron_decision",
        "checkin_dispatch_delivery",
        "resume_reconciliation",
        "shared_continuity_sqlite_repository",
        "hermes_handoff_gate",
        "gumi_hook_registry",
    }

    for entry in entries:
        assert entry["entrypoint"]
        assert entry["status"] in {
            "covered",
            "partial",
            "compatibility_surface",
            "not_live_default",
            "unresolved",
        }
        assert entry["claim"]
        assert entry["evidence"]["code_paths"]
        assert entry["evidence"]["test_paths"]
        assert set(entry["controls"]).issubset(
            {invariant["invariant_id"] for invariant in report["runtime_invariants"]}
        )


def test_runtime_path_coverage_flags_known_divergence_without_overclaiming():
    report = build_runtime_path_coverage_report()
    entries_by_id = {entry["path_id"]: entry for entry in report["path_inventory"]}

    legacy = entries_by_id["standalone_shared_continuity_legacy_hook"]
    assert legacy["status"] == "compatibility_surface"
    assert "adapter" in " ".join(legacy["gaps"]).lower()

    cron = entries_by_id["no_agent_cron_decision"]
    assert cron["status"] == "partial"
    assert any("fail-open" in gap for gap in cron["gaps"])

    dispatch = entries_by_id["checkin_dispatch_delivery"]
    assert "output_review" in dispatch["controls"]
    assert "delivery_gate" in dispatch["controls"]

    hermes_entry = entries_by_id["hermes_entry_transform_hook"]
    assert hermes_entry["status"] == "covered"
    assert "output_review" in hermes_entry["controls"]
    assert any(
        "test_hermes_entry.py" in path
        for path in hermes_entry["evidence"]["test_paths"]
    )
    assert "semantic" in " ".join(hermes_entry["evidence"]["arguments"]).lower()

    durable = entries_by_id["shared_continuity_sqlite_repository"]
    assert durable["status"] == "covered"
    assert "durable_continuity" in durable["controls"]
    assert any(
        "test_durable_sqlite_repository.py" in path
        for path in durable["evidence"]["test_paths"]
    )
    assert "backup/restore" in " ".join(durable["evidence"]["arguments"]).lower()
    assert not any(
        item == "Backup/restore and multi-week retention drills for the Shared Continuity SQLite backend."
        for item in report["next_required_evidence"]
    )


def test_eval_run_runtime_path_coverage_outputs_json(capsys):
    exit_code = eval_run.main(["--experiment", "runtime_path_coverage", "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "runtime_path_coverage_v1"
    assert output["claim_scope"] == "static_contract_inventory"
    assert output["summary"]["total_paths"] == len(output["path_inventory"])
