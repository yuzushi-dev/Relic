"""Synthetic multi-subject Shared Continuity isolation/load evidence."""

from __future__ import annotations

from scripts import eval_run
from relic.eval.multi_subject_isolation_load import (
    build_multi_subject_isolation_load_report,
)


def test_multi_subject_isolation_load_report_exercises_subject_scoping(tmp_path):
    report = build_multi_subject_isolation_load_report(
        db_path=tmp_path / "continuity-load.db",
        subject_count=6,
        researcher_count=3,
        markers_per_subject=3,
    )

    assert report["report_id"] == "multi_subject_isolation_load_v1"
    assert report["claim_scope"] == "synthetic_multi_subject_researcher_load"
    assert report["summary"]["subject_count"] == 6
    assert report["summary"]["researcher_count"] == 3
    assert report["summary"]["marker_create_attempt_count"] == 18
    assert report["summary"]["stored_marker_count"] == 18
    assert report["summary"]["cross_subject_leak_count"] == 0
    assert report["summary"]["event_subject_mismatch_count"] == 0
    assert report["summary"]["unconfirmed_candidate_recall_count"] == 0
    assert report["summary"]["all_invariants_passed"] is True
    assert report["validation"]["valid"] is True
    assert {
        "concurrent_subject_marker_writes",
        "subject_scoped_recent_marker_reads",
        "subject_scoped_audit_event_reads",
        "unconfirmed_candidates_excluded_from_runtime_recall",
    } <= set(report["validation"]["checked_rules"])


def test_multi_subject_isolation_load_report_excludes_volatile_runtime_fields(tmp_path):
    report = build_multi_subject_isolation_load_report(
        db_path=tmp_path / "continuity-load.db",
        subject_count=3,
        researcher_count=1,
        markers_per_subject=2,
    )

    assert "total_write_elapsed_ms" not in report["summary"]
    assert "mean_write_elapsed_ms" not in report["summary"]
    assert all(
        "candidate_marker_id" not in summary
        and "write_elapsed_ms" not in summary
        for summary in report["subject_summaries"]
    )


def test_eval_run_multi_subject_isolation_load_outputs_json(capsys):
    exit_code = eval_run.main(
        ["--experiment", "multi_subject_isolation_load", "--json"]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"report_id": "multi_subject_isolation_load_v1"' in output
