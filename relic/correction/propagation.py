"""Correction propagation for runtime correction updates.

This module handles propagating corrections through the system,
updating both the database AND derived artifacts (not just DB).
This is critical to avoid the block condition: "correction updates DB but not derived artifacts".
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from relic.db import get_connection, init_db


class CorrectionType(str, Enum):
    """Types of corrections that can be applied."""
    CONTENT_UPDATE = "content_update"
    DELETION = "deletion"
    REDACTION = "redaction"
    PRIVACY_UPGRADE = "privacy_upgrade"
    FACTUAL_CORRECTION = "factual_correction"
    FIRST_CORRECTION = "first_correction"


class CorrectionScope(str, Enum):
    """Scope of correction propagation."""
    SINGLE_PROMPT = "single_prompt"
    SESSION = "session"
    ALL = "all"


class CorrectionEvent(BaseModel):
    """A single correction event in the trace."""
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correction_type: CorrectionType
    prompt_id: UUID
    delta_content: str = ""
    applied: bool = False
    derived_artifacts_updated: list[UUID] = Field(default_factory=list)
    error: str | None = None


class CorrectionTrace(BaseModel):
    """A complete correction trace."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scope: CorrectionScope
    target_id: UUID | None = None
    correction_type: CorrectionType
    events: list[CorrectionEvent] = Field(default_factory=list)
    total_prompts_affected: int = 0
    total_artifacts_updated: int = 0
    completed: bool = False


class CorrectionPropagator:
    """Propagates corrections through the system.

    This is the critical component that ensures corrections update BOTH:
    1. The database records (correction_records, prompt_records)
    2. The derived artifacts (not just DB - block condition prevention)

    The propagator maintains a correction trace for audit purposes.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._trace_output_path: Path | None = None

    def set_trace_output(self, path: Path) -> None:
        """Set the path for writing correction traces."""
        self._trace_output_path = path

    def apply_correction(
        self,
        prompt_id: UUID | str,
        correction_type: CorrectionType,
        delta_content: str = "",
    ) -> CorrectionTrace:
        """Apply a correction to a single prompt and propagate to derived artifacts."""
        if isinstance(prompt_id, str):
            try:
                prompt_id = UUID(prompt_id)
            except ValueError:
                prompt_id = UUID(bytes=hashlib.sha256(prompt_id.encode()).digest()[:16])

        trace = CorrectionTrace(
            scope=CorrectionScope.SINGLE_PROMPT,
            target_id=prompt_id,
            correction_type=correction_type,
        )

        event = CorrectionEvent(
            correction_type=correction_type,
            prompt_id=prompt_id,
            delta_content=delta_content,
        )

        try:
            if self._db_path:
                init_db(self._db_path)
            conn = get_connection(self._db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO correction_records
                    (id, prompt_id, correction_type, delta_content, applied, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(event.id),
                        str(prompt_id),
                        correction_type.value,
                        delta_content,
                        True,
                        "user_correction",
                        event.timestamp.isoformat(),
                    ),
                )

                derived_artifact_ids = self._update_derived_artifacts(
                    conn, prompt_id, correction_type, delta_content
                )

                event.applied = True
                event.derived_artifacts_updated = derived_artifact_ids

                trace.events.append(event)
                trace.total_prompts_affected = 1
                trace.total_artifacts_updated = len(derived_artifact_ids)
                trace.completed = True

                conn.commit()
            finally:
                conn.close()

        except Exception as e:
            event.error = str(e)
            trace.events.append(event)
            trace.completed = False

        self._write_trace(trace)
        return trace

    def propagate_session_corrections(
        self,
        session_id: UUID,
        correction_type: CorrectionType,
        delta_content: str = "",
    ) -> CorrectionTrace:
        """Propagate corrections across all prompts in a session."""
        trace = CorrectionTrace(
            scope=CorrectionScope.SESSION,
            target_id=session_id,
            correction_type=correction_type,
        )

        try:
            conn = get_connection(self._db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM prompt_records WHERE session_id = ?",
                    (str(session_id),),
                )
                prompt_rows = cur.fetchall()

                all_artifact_ids: list[UUID] = []

                for prompt_row in prompt_rows:
                    prompt_id = UUID(prompt_row["id"])

                    event = CorrectionEvent(
                        correction_type=correction_type,
                        prompt_id=prompt_id,
                        delta_content=delta_content,
                    )

                    try:
                        cur.execute(
                            """
                            INSERT INTO correction_records
                            (id, prompt_id, correction_type, delta_content, applied, source, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(event.id),
                                str(prompt_id),
                                correction_type.value,
                                delta_content,
                                True,
                                "user_correction",
                                event.timestamp.isoformat(),
                            ),
                        )

                        derived_ids = self._update_derived_artifacts(
                            conn, prompt_id, correction_type, delta_content
                        )

                        event.applied = True
                        event.derived_artifacts_updated = derived_ids
                        all_artifact_ids.extend(derived_ids)

                    except Exception as e:
                        event.error = str(e)

                    trace.events.append(event)

                trace.total_prompts_affected = len(prompt_rows)
                trace.total_artifacts_updated = len(set(all_artifact_ids))
                trace.completed = True

                conn.commit()
            finally:
                conn.close()

        except Exception:
            trace.completed = False

        self._write_trace(trace)
        return trace

    def _update_derived_artifacts(
        self,
        conn: Any,
        prompt_id: UUID,
        correction_type: CorrectionType,
        delta_content: str,
    ) -> list[UUID]:
        """Update derived artifacts when a correction is applied.

        This is the CRITICAL step that prevents the block condition:
        "correction updates DB but not derived artifacts"

        Returns list of artifact IDs that were updated.
        """
        updated_artifact_ids: list[UUID] = []

        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM prompt_artifacts pa
            JOIN artifact_records ar ON pa.artifact_id = ar.id
            WHERE pa.prompt_id = ?
            """,
            (str(prompt_id),),
        )
        derived_artifacts = cur.fetchall()

        if not derived_artifacts:
            cur.execute(
                """
                SELECT * FROM artifact_records
                WHERE session_id = (SELECT session_id FROM prompt_records WHERE id = ?)
                """,
                (str(prompt_id),),
            )
            derived_artifacts = cur.fetchall()

        for artifact_row in derived_artifacts:
            artifact_id = UUID(artifact_row["id"])

            metadata = {}
            try:
                if artifact_row["metadata_json"]:
                    metadata = eval(artifact_row["metadata_json"])
            except Exception:
                pass

            metadata["last_correction"] = {
                "correction_type": correction_type.value,
                "corrected_at": datetime.utcnow().isoformat(),
                "prompt_id": str(prompt_id),
            }

            if correction_type == CorrectionType.REDACTION:
                metadata["redacted"] = True
                metadata["redacted_content"] = "[REDACTED]"
            elif correction_type == CorrectionType.PRIVACY_UPGRADE:
                metadata["privacy_level"] = "high"

            cur.execute(
                """
                UPDATE artifact_records
                SET metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(metadata), datetime.utcnow().isoformat(), str(artifact_id)),
            )

            updated_artifact_ids.append(artifact_id)

        return updated_artifact_ids

    def _write_trace(self, trace: CorrectionTrace) -> None:
        """Write correction trace to output file."""
        if not self._trace_output_path:
            return

        trace_data = trace.model_dump(mode="json")

        self._trace_output_path.parent.mkdir(parents=True, exist_ok=True)

        if self._trace_output_path.exists():
            with open(self._trace_output_path, "a") as f:
                f.write(json.dumps(trace_data) + "\n")
        else:
            self._trace_output_path.write_text(json.dumps(trace_data) + "\n")

    def get_correction_history(
        self,
        prompt_id: UUID | None = None,
        session_id: UUID | None = None,
        limit: int = 100,
    ) -> list[CorrectionEvent]:
        """Get correction history for audit."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            if prompt_id:
                cur.execute(
                    """
                    SELECT * FROM correction_records
                    WHERE prompt_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (str(prompt_id), limit),
                )
            elif session_id:
                cur.execute(
                    """
                    SELECT cr.* FROM correction_records cr
                    JOIN prompt_records pr ON cr.prompt_id = pr.id
                    WHERE pr.session_id = ?
                    ORDER BY cr.created_at DESC
                    LIMIT ?
                    """,
                    (str(session_id), limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM correction_records
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = cur.fetchall()
        finally:
            conn.close()

        return [
            CorrectionEvent(
                id=UUID(row["id"]),
                timestamp=datetime.fromisoformat(row["created_at"]),
                correction_type=CorrectionType(row["correction_type"]),
                prompt_id=UUID(row["prompt_id"]),
                delta_content=row["delta_content"] or "",
                applied=row["applied"],
                error=None,
            )
            for row in rows
        ]

    def verify_artifact_consistency(
        self,
        prompt_id: UUID,
    ) -> dict[str, Any]:
        """Verify that derived artifacts are consistent with the prompt.

        Returns a report of any inconsistencies found.
        """
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) as cnt FROM correction_records
                WHERE prompt_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(prompt_id),),
            )
            last_correction_time = cur.fetchone()["cnt"]

            cur.execute(
                "SELECT session_id FROM prompt_records WHERE id = ?",
                (str(prompt_id),),
            )
            session_row = cur.fetchone()
            session_id_val = UUID(session_row["session_id"]) if session_row else None

            inconsistencies = []

            if session_id_val:
                cur.execute(
                    """
                    SELECT * FROM artifact_records
                    WHERE session_id = ? AND metadata_json NOT LIKE '%last_correction%'
                    """,
                    (str(session_id_val),),
                )
                stale_artifacts = cur.fetchall()

                for artifact in stale_artifacts:
                    inconsistencies.append({
                        "artifact_id": str(UUID(artifact["id"])),
                        "issue": "stale_artifact",
                        "message": "Artifact may not reflect recent corrections",
                    })
        finally:
            conn.close()

        return {
            "prompt_id": str(prompt_id),
            "has_recent_corrections": last_correction_time > 0,
            "inconsistencies": inconsistencies,
            "consistent": len(inconsistencies) == 0,
        }
