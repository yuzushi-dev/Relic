"""Delete functionality with dry-run support.

This module provides safe deletion of user data with proper
invalidation of derived artifacts, replication bundles, and eval cases.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from relic.db import get_connection


class DeleteScope(str, Enum):
    """Scope of deletion."""
    PROMPT = "prompt"
    SESSION = "session"
    ALL = "all"


class AffectedArtifact(BaseModel):
    """An artifact affected by a delete operation."""
    id: UUID
    artifact_type: str
    artifact_hash: str
    session_id: UUID
    derived: bool = False
    replication_bundle: bool = False
    eval_case: bool = False


class DeleteDryRunResult(BaseModel):
    """Result of a delete dry-run."""
    id: UUID = Field(default_factory=uuid4)
    scope: DeleteScope
    target_id: UUID | None = None
    affected_prompts: int = 0
    affected_corrections: int = 0
    affected_artifacts: list[AffectedArtifact] = Field(default_factory=list)
    affected_replication_bundles: int = 0
    affected_eval_cases: int = 0
    warnings: list[str] = Field(default_factory=list)


class DeleteResult(BaseModel):
    """Result of an actual delete operation."""
    id: UUID = Field(default_factory=uuid4)
    scope: DeleteScope
    target_id: UUID | None = None
    deleted_prompts: int = 0
    deleted_corrections: int = 0
    deleted_artifacts: int = 0
    invalidated_replication_bundles: int = 0
    invalidated_eval_cases: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DeleteManager:
    """Manages secure deletion of user data.

    Delete operations must:
    1. List affected artifacts in dry-run mode
    2. Invalidate derived artifacts when applying
    3. Handle replication bundles and eval cases
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def dry_run(
        self,
        scope: DeleteScope,
        target_id: UUID | None = None,
    ) -> DeleteDryRunResult:
        """Preview what would be deleted without actually deleting."""
        result = DeleteDryRunResult(
            scope=scope,
            target_id=target_id,
        )

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()

            if scope == DeleteScope.PROMPT and target_id:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM prompt_records WHERE id = ?",
                    (str(target_id),),
                )
                result.affected_prompts = cur.fetchone()["cnt"]

                cur.execute(
                    "SELECT COUNT(*) as cnt FROM correction_records WHERE prompt_id = ?",
                    (str(target_id),),
                )
                result.affected_corrections = cur.fetchone()["cnt"]

            elif scope == DeleteScope.SESSION and target_id:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM prompt_records WHERE session_id = ?",
                    (str(target_id),),
                )
                result.affected_prompts = cur.fetchone()["cnt"]

                cur.execute(
                    """
                    SELECT COUNT(*) as cnt FROM correction_records
                    WHERE prompt_id IN (SELECT id FROM prompt_records WHERE session_id = ?)
                    """,
                    (str(target_id),),
                )
                result.affected_corrections = cur.fetchone()["cnt"]

            elif scope == DeleteScope.ALL:
                cur.execute("SELECT COUNT(*) as cnt FROM prompt_records")
                result.affected_prompts = cur.fetchone()["cnt"]

                cur.execute("SELECT COUNT(*) as cnt FROM correction_records")
                result.affected_corrections = cur.fetchone()["cnt"]

            result.affected_artifacts = self._get_affected_artifacts(conn, scope, target_id)
            result.affected_replication_bundles = self._count_replication_bundles(conn)
            result.affected_eval_cases = self._count_eval_cases(conn)
        finally:
            conn.close()

        return result

    def delete(
        self,
        scope: DeleteScope,
        target_id: UUID | None = None,
    ) -> DeleteResult:
        """Execute the delete operation and invalidate derived artifacts."""
        result = DeleteResult(
            scope=scope,
            target_id=target_id,
        )

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()

            if scope == DeleteScope.PROMPT and target_id:
                cur.execute(
                    "DELETE FROM prompt_records WHERE id = ?",
                    (str(target_id),),
                )
                result.deleted_prompts = cur.rowcount

                cur.execute(
                    "DELETE FROM correction_records WHERE prompt_id = ?",
                    (str(target_id),),
                )
                result.deleted_corrections = cur.rowcount

            elif scope == DeleteScope.SESSION and target_id:
                cur.execute(
                    "DELETE FROM prompt_records WHERE session_id = ?",
                    (str(target_id),),
                )
                result.deleted_prompts = cur.rowcount

                cur.execute(
                    """
                    DELETE FROM correction_records
                    WHERE prompt_id IN (SELECT id FROM prompt_records WHERE session_id = ?)
                    """,
                    (str(target_id),),
                )
                result.deleted_corrections = cur.rowcount

            elif scope == DeleteScope.ALL:
                cur.execute("DELETE FROM prompt_records")
                result.deleted_prompts = cur.rowcount

                cur.execute("DELETE FROM correction_records")
                result.deleted_corrections = cur.rowcount

            result.invalidated_replication_bundles = self._invalidate_replication_bundles(conn)
            result.invalidated_eval_cases = self._invalidate_eval_cases(conn)
            result.deleted_artifacts = self._invalidate_artifacts(conn, scope, target_id)

            conn.commit()
        finally:
            conn.close()

        return result

    def _get_affected_artifacts(
        self,
        conn: Any,
        scope: DeleteScope,
        target_id: UUID | None = None,
    ) -> list[AffectedArtifact]:
        """Get list of artifacts that would be affected."""
        artifacts = []

        cur = conn.cursor()
        if scope == DeleteScope.SESSION and target_id:
            cur.execute(
                "SELECT * FROM artifact_records WHERE session_id = ?",
                (str(target_id),),
            )
        elif scope == DeleteScope.ALL:
            cur.execute("SELECT * FROM artifact_records")
        else:
            return artifacts

        for row in cur.fetchall():
            metadata = {}
            try:
                if row["metadata_json"]:
                    metadata = eval(row["metadata_json"])
            except Exception:
                pass

            artifact = AffectedArtifact(
                id=UUID(row["id"]),
                artifact_type=row["artifact_type"],
                artifact_hash=row["artifact_hash"],
                session_id=UUID(row["session_id"]) if row["session_id"] else uuid4(),
                derived=metadata.get("derived", False),
                replication_bundle=metadata.get("replication_bundle", False),
                eval_case=metadata.get("eval_case", False),
            )
            artifacts.append(artifact)

        return artifacts

    def _count_replication_bundles(self, conn: Any) -> int:
        """Count replication bundles in artifact registry."""
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM artifact_records
            WHERE metadata_json LIKE '%replication_bundle%'
            """
        )
        return cur.fetchone()["cnt"]

    def _count_eval_cases(self, conn: Any) -> int:
        """Count eval cases in artifact registry."""
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM artifact_records
            WHERE metadata_json LIKE '%eval_case%'
            """
        )
        return cur.fetchone()["cnt"]

    def _invalidate_artifacts(
        self,
        conn: Any,
        scope: DeleteScope,
        target_id: UUID | None = None,
    ) -> int:
        """Invalidate artifacts associated with deleted data."""
        cur = conn.cursor()
        deleted = 0
        now = datetime.utcnow().isoformat()

        if scope == DeleteScope.SESSION and target_id:
            cur.execute("SELECT id, metadata_json FROM artifact_records WHERE session_id = ?",
                        (str(target_id),))
            for row in cur.fetchall():
                metadata = self._update_metadata_field(row["metadata_json"], "invalidated", True, now)
                cur.execute("UPDATE artifact_records SET metadata_json = ?, updated_at = ? WHERE id = ?",
                            (json.dumps(metadata), now, row["id"]))
                deleted += 1
        elif scope == DeleteScope.ALL:
            cur.execute("SELECT id, metadata_json FROM artifact_records")
            for row in cur.fetchall():
                metadata = self._update_metadata_field(row["metadata_json"], "invalidated", True, now)
                cur.execute("UPDATE artifact_records SET metadata_json = ?, updated_at = ? WHERE id = ?",
                            (json.dumps(metadata), now, row["id"]))
                deleted += 1

        return deleted

    def _update_metadata_field(
        self,
        metadata_json: str,
        key: str,
        value: Any,
        timestamp: str,
    ) -> dict:
        """Update a single field in metadata JSON, preserving other fields."""
        metadata = {}
        try:
            if metadata_json:
                metadata = json.loads(metadata_json) if metadata_json.startswith("{") else eval(metadata_json)
        except Exception:
            pass
        metadata[key] = value
        metadata["updated_at"] = timestamp
        return metadata

    def _invalidate_replication_bundles(self, conn: Any) -> int:
        """Invalidate all replication bundles."""
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        invalidated = 0

        cur.execute("SELECT id, metadata_json FROM artifact_records WHERE metadata_json LIKE '%replication_bundle%'")
        for row in cur.fetchall():
            metadata = self._update_metadata_field(row["metadata_json"], "replication_bundle_invalidated", True, now)
            cur.execute(
                "UPDATE artifact_records SET metadata_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(metadata), now, row["id"]),
            )
            invalidated += 1

        return invalidated

    def _invalidate_eval_cases(self, conn: Any) -> int:
        """Invalidate all eval cases."""
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        invalidated = 0

        cur.execute("SELECT id, metadata_json FROM artifact_records WHERE metadata_json LIKE '%eval_case%'")
        for row in cur.fetchall():
            metadata = self._update_metadata_field(row["metadata_json"], "eval_case_invalidated", True, now)
            cur.execute(
                "UPDATE artifact_records SET metadata_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(metadata), now, row["id"]),
            )
            invalidated += 1

        return invalidated
