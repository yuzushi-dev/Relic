"""Chronicle audit reconstruction coverage report contract tests."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.chronicle_audit_coverage import build_chronicle_audit_coverage_report


def test_chronicle_audit_coverage_report_has_scope_and_limitations():
    report = build_chronicle_audit_coverage_report()

    assert report["report_id"] == "chronicle_audit_coverage_v1"
    assert report["claim_scope"] == "static_query_reconstruction_inventory"
    assert report["methodology"]["evidence_model"] == "audit_trail_reconstruction_matrix"
    assert report["methodology"]["provenance_model"] == "W3C_PROV_O_aligned"
    assert "not live runtime telemetry" in " ".join(report["limitations"])
    assert "not a cryptographically signed or Merkle-chained ledger" in " ".join(
        report["limitations"]
    )
    assert report["summary"]["reconstruction_questions"] >= 23
    assert report["summary"]["supported_questions"] >= 20
    assert report["summary"]["global_audit_claim_supported"] is False


def test_chronicle_reconstruction_questions_are_queryable_and_traceable():
    report = build_chronicle_audit_coverage_report()
    questions = report["reconstruction_questions"]

    question_ids = {item["question_id"] for item in questions}
    assert question_ids >= {
        "Q01_session_timeline",
        "Q03_model_called",
        "Q05_response_hash",
        "Q08_memory_reads",
        "Q13_decision_records",
        "Q18_provenance_subgraph",
        "Q21_subject_export_count",
        "Q23_retention_policy_counts",
    }

    for item in questions:
        assert item["question"]
        assert item["status"] in {"supported", "partial", "unsupported"}
        assert item["query_surface"]
        assert item["required_records"]
        assert item["evidence"]["code_paths"]
        assert item["evidence"]["test_paths"]


def test_chronicle_audit_capabilities_cover_schema_query_integrity_and_governance():
    report = build_chronicle_audit_coverage_report()
    capabilities = {item["capability_id"]: item for item in report["audit_capabilities"]}

    assert set(capabilities) >= {
        "event_schema",
        "decision_schema",
        "trace_join",
        "subject_query",
        "provenance_graph",
        "access_audit",
        "retention_reaper",
        "export_bundle",
        "journal_verify_repair",
        "payload_hashing",
        "redaction_guard",
        "consent_basis",
    }
    assert capabilities["journal_verify_repair"]["status"] == "partial"
    assert capabilities["payload_hashing"]["status"] == "partial"
    assert "hash chain" in " ".join(capabilities["payload_hashing"]["gaps"]).lower()


def test_chronicle_required_fields_are_declared_for_event_and_decision_reconstruction():
    report = build_chronicle_audit_coverage_report()
    fields = report["minimum_reconstruction_fields"]

    event_fields = set(fields["chronicle_event"])
    decision_fields = set(fields["chronicle_decision"])
    assert event_fields >= {
        "event_id",
        "event_type",
        "event_category",
        "trace_id",
        "subject_id",
        "source_module",
        "timestamp",
        "payload_hash",
        "retention_policy",
    }
    assert decision_fields >= {
        "decision_id",
        "trace_id",
        "decision_kind",
        "selected_action",
        "evidence_refs",
        "rationale_summary",
        "validation_status",
    }


def test_eval_run_chronicle_audit_coverage_outputs_json(capsys):
    exit_code = eval_run.main(["--experiment", "chronicle_audit_coverage", "--json"])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "chronicle_audit_coverage_v1"
    assert output["summary"]["reconstruction_questions"] == len(
        output["reconstruction_questions"]
    )
