"""Durable Shared Continuity repository contract tests."""

from __future__ import annotations

from relic.shared_continuity.repository import SQLiteContinuityRepository
from relic.shared_continuity.service import ContinuityService


def test_confirmed_marker_survives_service_restart(tmp_path):
    db_path = tmp_path / "continuity.db"

    first_service = ContinuityService(
        repository=SQLiteContinuityRepository(db_path)
    )
    marker = first_service.remember(
        subject_id="subj_001",
        gumi_instance_id="gumi_001",
        hermes_profile_id="hermes_001",
        subject_words=["I call this my quiet Friday ritual"],
        source_type="subject_confirmed",
        gumi_agreed_words=["quiet Friday ritual"],
        max_recall_count=4,
        ttl_seconds=3600,
        subject_confirmation=True,
    )

    restarted_service = ContinuityService(
        repository=SQLiteContinuityRepository(db_path)
    )

    recalled = restarted_service.recent_markers(
        subject_id="subj_001",
        gumi_instance_id="gumi_001",
        hermes_profile_id="hermes_001",
    )
    assert [item["marker_id"] for item in recalled] == [marker["marker_id"]]
    assert recalled[0]["subject_words"] == ["I call this my quiet Friday ritual"]
    assert recalled[0]["max_recall_count"] == 4


def test_authoritative_correction_chain_survives_restart(tmp_path):
    db_path = tmp_path / "continuity.db"
    service = ContinuityService(repository=SQLiteContinuityRepository(db_path))
    marker = service.remember(
        subject_id="subj_001",
        gumi_instance_id="gumi_001",
        hermes_profile_id="hermes_001",
        subject_words=["Friday is my reset day"],
        source_type="subject_confirmed",
        subject_confirmation=True,
    )

    correction = service.correct(
        marker_id=marker["marker_id"],
        subject_id="subj_001",
        gumi_instance_id="gumi_001",
        hermes_profile_id="hermes_001",
        subject_words=["Saturday is my reset day"],
    )

    restarted_service = ContinuityService(
        repository=SQLiteContinuityRepository(db_path)
    )

    recalled = restarted_service.recent_markers(subject_id="subj_001")
    assert [item["marker_id"] for item in recalled] == [
        correction["new_marker_id"]
    ]
    assert recalled[0]["final_subject_words"] == ["Saturday is my reset day"]


def test_marker_level_audit_events_are_durable_and_queryable(tmp_path):
    db_path = tmp_path / "continuity.db"
    repository = SQLiteContinuityRepository(db_path)
    service = ContinuityService(repository=repository)
    marker = service.remember(
        subject_id="subj_001",
        gumi_instance_id="gumi_001",
        hermes_profile_id="hermes_001",
        subject_words=["Please remember my garden project"],
        source_type="subject_confirmed",
        subject_confirmation=True,
    )

    service.forget(marker_id=marker["marker_id"], subject_id="subj_001")

    restarted_repository = SQLiteContinuityRepository(db_path)
    events = restarted_repository.list_events(
        subject_id="subj_001",
        marker_id=marker["marker_id"],
    )

    assert [event["event_type"] for event in events] == [
        "marker_created",
        "marker_forgotten",
    ]
    assert all(event["subject_id"] == "subj_001" for event in events)
    assert all(event["marker_id"] == marker["marker_id"] for event in events)


def test_verified_backup_restores_markers_and_events(tmp_path):
    db_path = tmp_path / "continuity.db"
    backup_path = tmp_path / "continuity.backup.db"
    restored_path = tmp_path / "restored.db"

    repository = SQLiteContinuityRepository(db_path)
    service = ContinuityService(repository=repository)
    marker = service.remember(
        subject_id="subj_001",
        gumi_instance_id="gumi_001",
        hermes_profile_id="hermes_001",
        subject_words=["Keep my pottery class in mind"],
        source_type="subject_confirmed",
        subject_confirmation=True,
    )
    service.forget(marker_id=marker["marker_id"], subject_id="subj_001")

    backup_manifest = repository.create_verified_backup(backup_path)

    assert backup_manifest["backup_path"] == str(backup_path)
    assert backup_manifest["integrity_check"] == "ok"
    assert backup_manifest["row_counts"]["continuity_marker"] == 1
    assert backup_manifest["row_counts"]["continuity_event"] == 2
    assert backup_manifest["backup_sha256"].startswith("sha256:")

    restore_manifest = SQLiteContinuityRepository.restore_verified_backup(
        backup_path=backup_path,
        target_db_path=restored_path,
        expected_backup_sha256=backup_manifest["backup_sha256"],
    )
    restored_repository = SQLiteContinuityRepository(restored_path)
    restored_service = ContinuityService(repository=restored_repository)

    assert restore_manifest["restored_integrity_check"] == "ok"
    assert restore_manifest["restored_row_counts"]["continuity_marker"] == 1
    assert restored_service.recent_markers(subject_id="subj_001") == []
    restored_events = restored_repository.list_events(
        subject_id="subj_001",
        marker_id=marker["marker_id"],
    )
    assert [event["event_type"] for event in restored_events] == [
        "marker_created",
        "marker_forgotten",
    ]


def test_verified_restore_rejects_corrupt_backup(tmp_path):
    backup_path = tmp_path / "corrupt.db"
    restored_path = tmp_path / "restored.db"
    backup_path.write_text("not a sqlite database", encoding="utf-8")

    try:
        SQLiteContinuityRepository.restore_verified_backup(
            backup_path=backup_path,
            target_db_path=restored_path,
        )
    except ValueError as exc:
        assert "integrity" in str(exc).lower() or "sqlite" in str(exc).lower()
    else:
        raise AssertionError("corrupt backup was restored")
