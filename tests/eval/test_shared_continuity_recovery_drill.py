"""Shared Continuity backup/restore recovery drill contract tests."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.shared_continuity_recovery import (
    build_shared_continuity_recovery_drill_report,
)


def test_shared_continuity_recovery_drill_reports_verified_restore():
    report = build_shared_continuity_recovery_drill_report()

    assert report["report_id"] == "shared_continuity_recovery_drill_v1"
    assert report["claim_scope"] == "synthetic_repository_recovery_drill"
    assert report["methodology"]["sqlite_backup_method"] == "sqlite_backup_api"
    assert report["methodology"]["integrity_check"] == "PRAGMA integrity_check"
    assert report["summary"]["backup_integrity_ok"] is True
    assert report["summary"]["restore_integrity_ok"] is True
    assert report["summary"]["checksum_verified"] is True
    assert report["summary"]["active_marker_recalled_after_restore"] is True
    assert report["summary"]["forgotten_marker_not_recalled_after_restore"] is True
    assert report["summary"]["marker_events_restored"] is True
    assert report["backup_manifest"]["row_counts"]["continuity_marker"] >= 2
    assert report["restore_manifest"]["restored_row_counts"]["continuity_event"] >= 3
    assert "not live Hermes deployment telemetry" in " ".join(report["limitations"])


def test_eval_run_shared_continuity_recovery_drill_outputs_json(capsys):
    exit_code = eval_run.main(
        ["--experiment", "shared_continuity_recovery_drill", "--json"]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "shared_continuity_recovery_drill_v1"
    assert output["summary"]["restore_integrity_ok"] is True
