"""SQLite persistence for Shared Continuity state."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from relic.db import get_connection, init_db
from relic.shared_continuity.service import (
    ContinuityCorrection,
    ContinuityMarker,
    MarkerStatus,
)


class SQLiteContinuityRepository:
    """Durable SQLite repository for marker-level Shared Continuity state."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        init_db(self.db_path)

    def load_state(self) -> dict[str, dict[str, Any]]:
        """Load persisted continuity state into service dictionaries."""
        conn = get_connection(self.db_path)
        try:
            markers = {
                row["marker_id"]: self._row_to_marker(row)
                for row in conn.execute("SELECT * FROM continuity_marker")
            }
            corrections = {
                row["correction_id"]: self._row_to_correction(row)
                for row in conn.execute("SELECT * FROM continuity_correction")
            }
            scopes = {
                row["scope_key"]: self._row_to_scope(row)
                for row in conn.execute("SELECT * FROM continuity_scope")
            }
        finally:
            conn.close()
        return {
            "markers": markers,
            "followups": {},
            "corrections": corrections,
            "scopes": scopes,
        }

    def save_marker(self, marker: ContinuityMarker) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO continuity_marker (
                    marker_id, subject_id, gumi_instance_id, hermes_profile_id,
                    subject_confirmation, source_type, created_at,
                    subject_words_json, gumi_agreed_words_json, raw_source_text,
                    status, gumi_recall_allowed, recall_count, max_recall_count,
                    ttl_seconds, expires_at, updated_at, candidate_for_confirmation,
                    clinical_interpretation_allowed, previous_version_id,
                    final_subject_words_json, next_version_id, normalized_tags_json,
                    gumi_words_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    marker.marker_id,
                    marker.subject_id,
                    marker.gumi_instance_id,
                    marker.hermes_profile_id,
                    int(marker.subject_confirmation),
                    marker.source_type,
                    marker.created_at,
                    self._dumps(marker.subject_words),
                    self._dumps(marker.gumi_agreed_words),
                    marker.raw_source_text,
                    self._enum_value(marker.status),
                    int(marker.gumi_recall_allowed),
                    marker.recall_count,
                    marker.max_recall_count,
                    marker.ttl_seconds,
                    marker.expires_at,
                    marker.updated_at,
                    int(marker.candidate_for_confirmation),
                    int(marker.clinical_interpretation_allowed),
                    marker.previous_version_id,
                    self._dumps_or_none(marker.final_subject_words),
                    marker.next_version_id,
                    self._dumps_or_none(marker.normalized_tags),
                    self._dumps_or_none(marker.gumi_words),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def save_correction(self, correction: ContinuityCorrection) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO continuity_correction (
                    correction_id, marker_id, subject_id, gumi_instance_id,
                    hermes_profile_id, authoritative, subject_words_json,
                    gumi_agreed_words_json, correction_note, status, created_at,
                    created_by, original_marker_id, is_replacement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    correction.correction_id,
                    correction.marker_id,
                    correction.subject_id,
                    correction.gumi_instance_id,
                    correction.hermes_profile_id,
                    int(correction.authoritative),
                    self._dumps(correction.subject_words),
                    self._dumps(correction.gumi_agreed_words),
                    correction.correction_note,
                    correction.status,
                    correction.created_at,
                    correction.created_by,
                    correction.original_marker_id,
                    int(correction.is_replacement),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def save_scope(self, scope_key: str, scope: dict[str, Any]) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO continuity_scope (
                    scope_key, subject_id, gumi_instance_id, hermes_profile_id,
                    scope_name, is_paused, paused_at, resumed_at, scope_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope_key,
                    scope["subject_id"],
                    scope.get("gumi_instance_id"),
                    scope.get("hermes_profile_id"),
                    scope["scope_name"],
                    int(scope.get("is_paused", False)),
                    scope.get("paused_at"),
                    scope.get("resumed_at"),
                    self._dumps(scope),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_subject(self, subject_id: str) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute("DELETE FROM continuity_correction WHERE subject_id = ?", (subject_id,))
            conn.execute("DELETE FROM continuity_marker WHERE subject_id = ?", (subject_id,))
            conn.execute("DELETE FROM continuity_scope WHERE subject_id = ?", (subject_id,))
            conn.commit()
        finally:
            conn.close()

    def append_event(
        self,
        *,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        event_type: str,
        marker_id: str | None = None,
        followup_id: str | None = None,
        correction_id: str | None = None,
        event_data: dict[str, Any] | None = None,
        source: str = "service",
        subject_visible: bool = False,
    ) -> dict[str, Any]:
        event = {
            "event_id": f"continuity_event_{uuid.uuid4().hex}",
            "subject_id": subject_id,
            "gumi_instance_id": gumi_instance_id,
            "hermes_profile_id": hermes_profile_id,
            "event_type": event_type,
            "marker_id": marker_id,
            "followup_id": followup_id,
            "correction_id": correction_id,
            "event_data": event_data or {},
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "subject_visible": subject_visible,
        }
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO continuity_event (
                    event_id, subject_id, gumi_instance_id, hermes_profile_id,
                    event_type, marker_id, followup_id, correction_id,
                    event_data_json, source, created_at, subject_visible
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["subject_id"],
                    event["gumi_instance_id"],
                    event["hermes_profile_id"],
                    event["event_type"],
                    event["marker_id"],
                    event["followup_id"],
                    event["correction_id"],
                    self._dumps(event["event_data"]),
                    event["source"],
                    event["created_at"],
                    int(event["subject_visible"]),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return event

    def list_events(
        self,
        *,
        subject_id: str,
        marker_id: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM continuity_event WHERE subject_id = ?"
        params: list[Any] = [subject_id]
        if marker_id is not None:
            sql += " AND marker_id = ?"
            params.append(marker_id)
        sql += " ORDER BY sequence_id"

        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_event(row) for row in rows]

    def create_verified_backup(self, backup_path: str | Path) -> dict[str, Any]:
        """Create and verify a SQLite backup snapshot for recovery drills."""
        destination_path = Path(backup_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if destination_path.exists():
            destination_path.unlink()

        source = get_connection(self.db_path)
        destination = sqlite3.connect(str(destination_path))
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
            source.close()

        verification = self.verify_backup(destination_path)
        return {
            "backup_path": str(destination_path),
            "source_db_path": str(self.db_path),
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **verification,
        }

    @classmethod
    def restore_verified_backup(
        cls,
        *,
        backup_path: str | Path,
        target_db_path: str | Path,
        expected_backup_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Restore a verified backup into a target SQLite database."""
        source_path = Path(backup_path)
        target_path = Path(target_db_path)
        backup_verification = cls.verify_backup(
            source_path,
            expected_backup_sha256=expected_backup_sha256,
        )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            target_path.unlink()

        source = sqlite3.connect(str(source_path))
        destination = sqlite3.connect(str(target_path))
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
            source.close()

        restored_verification = cls.verify_backup(target_path)
        return {
            "backup_path": str(source_path),
            "target_db_path": str(target_path),
            "backup_sha256": backup_verification["backup_sha256"],
            "restored_sha256": restored_verification["backup_sha256"],
            "backup_integrity_check": backup_verification["integrity_check"],
            "restored_integrity_check": restored_verification["integrity_check"],
            "backup_row_counts": backup_verification["row_counts"],
            "restored_row_counts": restored_verification["row_counts"],
            "restored_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    @classmethod
    def verify_backup(
        cls,
        backup_path: str | Path,
        *,
        expected_backup_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Verify a SQLite backup with checksum, integrity check, and row counts."""
        path = Path(backup_path)
        if not path.exists():
            raise ValueError(f"backup file does not exist: {path}")

        digest = cls._file_sha256(path)
        if expected_backup_sha256 is not None and digest != expected_backup_sha256:
            raise ValueError("backup checksum mismatch")

        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError(f"backup integrity check failed: {integrity}")
            row_counts = cls._continuity_row_counts(conn)
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"backup sqlite integrity check failed: {exc}") from exc
        finally:
            conn.close()

        return {
            "backup_sha256": digest,
            "integrity_check": integrity,
            "row_counts": row_counts,
        }

    def _row_to_marker(self, row: Any) -> ContinuityMarker:
        return ContinuityMarker(
            marker_id=row["marker_id"],
            subject_id=row["subject_id"],
            gumi_instance_id=row["gumi_instance_id"],
            hermes_profile_id=row["hermes_profile_id"],
            subject_confirmation=bool(row["subject_confirmation"]),
            source_type=row["source_type"],
            created_at=row["created_at"],
            subject_words=self._loads(row["subject_words_json"]),
            gumi_agreed_words=self._loads(row["gumi_agreed_words_json"]),
            raw_source_text=row["raw_source_text"],
            status=MarkerStatus(row["status"]),
            gumi_recall_allowed=bool(row["gumi_recall_allowed"]),
            recall_count=row["recall_count"],
            max_recall_count=row["max_recall_count"],
            ttl_seconds=row["ttl_seconds"],
            expires_at=row["expires_at"],
            updated_at=row["updated_at"],
            candidate_for_confirmation=bool(row["candidate_for_confirmation"]),
            clinical_interpretation_allowed=bool(row["clinical_interpretation_allowed"]),
            previous_version_id=row["previous_version_id"],
            final_subject_words=self._loads_or_none(row["final_subject_words_json"]),
            next_version_id=row["next_version_id"],
            normalized_tags=self._loads_or_none(row["normalized_tags_json"]),
            gumi_words=self._loads_or_none(row["gumi_words_json"]),
        )

    def _row_to_correction(self, row: Any) -> ContinuityCorrection:
        return ContinuityCorrection(
            correction_id=row["correction_id"],
            marker_id=row["marker_id"],
            subject_id=row["subject_id"],
            gumi_instance_id=row["gumi_instance_id"],
            hermes_profile_id=row["hermes_profile_id"],
            authoritative=bool(row["authoritative"]),
            subject_words=self._loads(row["subject_words_json"]),
            gumi_agreed_words=self._loads(row["gumi_agreed_words_json"]),
            correction_note=row["correction_note"],
            status=row["status"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            original_marker_id=row["original_marker_id"],
            is_replacement=bool(row["is_replacement"]),
        )

    def _row_to_scope(self, row: Any) -> dict[str, Any]:
        scope = self._loads(row["scope_json"])
        scope["is_paused"] = bool(row["is_paused"])
        return scope

    def _row_to_event(self, row: Any) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "subject_id": row["subject_id"],
            "gumi_instance_id": row["gumi_instance_id"],
            "hermes_profile_id": row["hermes_profile_id"],
            "event_type": row["event_type"],
            "marker_id": row["marker_id"],
            "followup_id": row["followup_id"],
            "correction_id": row["correction_id"],
            "event_data": self._loads(row["event_data_json"]),
            "source": row["source"],
            "created_at": row["created_at"],
            "subject_visible": bool(row["subject_visible"]),
        }

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _continuity_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
        tables = [
            "continuity_marker",
            "continuity_correction",
            "continuity_scope",
            "continuity_event",
        ]
        counts: dict[str, int] = {}
        for table in tables:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            counts[table] = 0 if exists is None else conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
        return counts

    @staticmethod
    def _enum_value(value: Any) -> str:
        return value.value if hasattr(value, "value") else str(value)

    @staticmethod
    def _dumps(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _dumps_or_none(cls, value: Any) -> str | None:
        if value is None:
            return None
        return cls._dumps(value)

    @staticmethod
    def _loads(value: str) -> Any:
        return json.loads(value)

    @classmethod
    def _loads_or_none(cls, value: str | None) -> Any:
        if value is None:
            return None
        return cls._loads(value)
