"""Synthetic Shared Continuity SQLite recovery drill."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from relic.shared_continuity.repository import SQLiteContinuityRepository
from relic.shared_continuity.service import ContinuityService


def build_shared_continuity_recovery_drill_report() -> dict[str, Any]:
    """Run a synthetic backup/restore drill for Shared Continuity SQLite state."""
    with tempfile.TemporaryDirectory(prefix="relic-continuity-recovery-") as tmp:
        root = Path(tmp)
        db_path = root / "continuity.db"
        backup_path = root / "continuity.backup.db"
        restored_path = root / "continuity.restored.db"

        repository = SQLiteContinuityRepository(db_path)
        service = ContinuityService(repository=repository)

        active_marker = service.remember(
            subject_id="subj_recovery",
            gumi_instance_id="gumi_recovery",
            hermes_profile_id="hermes_recovery",
            subject_words=["Remember my Sunday bread project"],
            source_type="subject_confirmed",
            subject_confirmation=True,
        )
        forgotten_marker = service.remember(
            subject_id="subj_recovery",
            gumi_instance_id="gumi_recovery",
            hermes_profile_id="hermes_recovery",
            subject_words=["Remember the old pottery schedule"],
            source_type="subject_confirmed",
            subject_confirmation=True,
        )
        service.forget(
            marker_id=forgotten_marker["marker_id"],
            subject_id="subj_recovery",
        )

        backup_manifest = repository.create_verified_backup(backup_path)
        restore_manifest = SQLiteContinuityRepository.restore_verified_backup(
            backup_path=backup_path,
            target_db_path=restored_path,
            expected_backup_sha256=backup_manifest["backup_sha256"],
        )

        restored_repository = SQLiteContinuityRepository(restored_path)
        restored_service = ContinuityService(repository=restored_repository)
        recalled = restored_service.recent_markers(
            subject_id="subj_recovery",
            gumi_instance_id="gumi_recovery",
            hermes_profile_id="hermes_recovery",
        )
        recalled_ids = {marker["marker_id"] for marker in recalled}
        forgotten_events = restored_repository.list_events(
            subject_id="subj_recovery",
            marker_id=forgotten_marker["marker_id"],
        )

    summary = {
        "backup_integrity_ok": backup_manifest["integrity_check"] == "ok",
        "restore_integrity_ok": restore_manifest["restored_integrity_check"] == "ok",
        "checksum_verified": restore_manifest["backup_sha256"]
        == backup_manifest["backup_sha256"],
        "active_marker_recalled_after_restore": active_marker["marker_id"] in recalled_ids,
        "forgotten_marker_not_recalled_after_restore": forgotten_marker["marker_id"]
        not in recalled_ids,
        "marker_events_restored": [event["event_type"] for event in forgotten_events]
        == ["marker_created", "marker_forgotten"],
    }

    return {
        "report_id": "shared_continuity_recovery_drill_v1",
        "claim_scope": "synthetic_repository_recovery_drill",
        "methodology": {
            "sqlite_backup_method": "sqlite_backup_api",
            "integrity_check": "PRAGMA integrity_check",
            "checksum_algorithm": "sha256",
            "fixture_type": "synthetic_subject_scoped_marker_lifecycle",
        },
        "backup_manifest": backup_manifest,
        "restore_manifest": restore_manifest,
        "summary": summary,
        "limitations": [
            "This is not live Hermes deployment telemetry.",
            "This is not participant evidence, clinical validation, or a production disaster-recovery exercise.",
            "The drill uses a synthetic temporary SQLite database, not a multi-week study database.",
            "It does not prove off-host backup scheduling, retention policy compliance, or restore-time objectives.",
        ],
        "next_required_evidence": [
            "Run the drill against a staging Hermes profile database before a study deployment.",
            "Add scheduled/off-host backup policy evidence and restore-time measurements.",
            "Repeat after multi-week pilot data exists and compare expected versus restored row counts.",
        ],
    }
