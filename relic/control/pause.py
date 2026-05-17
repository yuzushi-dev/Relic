"""Pause and resume control for runtime governance.

This module provides pause functionality that disables CAC injection
when paused, ensuring user control is respected.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from relic.db import get_connection


class PauseState(str, Enum):
    """Possible pause states."""
    ACTIVE = "active"
    PAUSED = "paused"


class PauseRecord(BaseModel):
    """Record of a pause action."""
    id: UUID = Field(default_factory=uuid4)
    state: PauseState
    initiated_at: datetime = Field(default_factory=datetime.utcnow)
    resumed_at: datetime | None = None
    session_id: UUID | None = None
    reason: str = ""


class PauseController:
    """Controls pause/resume state with CAC injection control.

    When paused, CAC (Consent And Correction) injection is disabled
    to give users full control over their session.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def is_paused(self, session_id: UUID | None = None) -> bool:
        """Check if the session is currently paused."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT state, resumed_at FROM pause_records
                WHERE session_id IS ? AND state = ?
                ORDER BY initiated_at DESC
                LIMIT 1
                """,
                (str(session_id) if session_id else None, PauseState.PAUSED.value),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return False

        if row["resumed_at"]:
            return False

        return True

    def is_any_session_paused(self) -> bool:
        """Check if ANY session is currently paused (global check for cron use).

        Unlike is_paused(session_id), this finds pause records created by
        /relic pause (which stores a real session UUID, not NULL).
        Returns True if at least one active, non-resumed PAUSED record exists.
        """
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id FROM pause_records
                WHERE state = ? AND resumed_at IS NULL
                ORDER BY initiated_at DESC
                LIMIT 1
                """,
                (PauseState.PAUSED.value,),
            )
            row = cur.fetchone()
        finally:
            conn.close()
        return row is not None

    def pause(
        self,
        session_id: UUID | None = None,
        reason: str = "user_initiated",
    ) -> PauseRecord:
        """Pause the session, disabling CAC injection."""
        record = PauseRecord(
            state=PauseState.PAUSED,
            session_id=session_id,
            reason=reason,
        )

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO pause_records
                (id, state, initiated_at, session_id, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(record.id),
                    record.state.value,
                    record.initiated_at.isoformat(),
                    str(session_id) if session_id else None,
                    reason,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return record

    def resume(
        self,
        session_id: UUID | None = None,
    ) -> PauseRecord:
        """Resume the session, re-enabling CAC injection."""
        now = datetime.utcnow()

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE pause_records
                SET state = ?, resumed_at = ?
                WHERE session_id IS ? AND state = ? AND resumed_at IS NULL
                """,
                (
                    PauseState.ACTIVE.value,
                    now.isoformat(),
                    str(session_id) if session_id else None,
                    PauseState.PAUSED.value,
                ),
            )

            cur.execute(
                """
                SELECT * FROM pause_records
                WHERE session_id IS ? AND state = ?
                ORDER BY initiated_at DESC
                LIMIT 1
                """,
                (str(session_id) if session_id else None, PauseState.ACTIVE.value),
            )
            row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()

        if row:
            return PauseRecord(
                id=UUID(row["id"]),
                state=PauseState(row["state"]),
                initiated_at=datetime.fromisoformat(row["initiated_at"]),
                resumed_at=datetime.fromisoformat(row["resumed_at"]) if row["resumed_at"] else None,
                session_id=UUID(row["session_id"]) if row["session_id"] else None,
                reason=row["reason"] or "",
            )

        record = PauseRecord(
            state=PauseState.ACTIVE,
            resumed_at=now,
            session_id=session_id,
            reason="resume",
        )

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO pause_records
                (id, state, initiated_at, resumed_at, session_id, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.id),
                    record.state.value,
                    record.initiated_at.isoformat(),
                    record.resumed_at.isoformat() if record.resumed_at else None,
                    str(session_id) if session_id else None,
                    record.reason,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return record

    def get_pause_history(
        self,
        session_id: UUID | None = None,
        limit: int = 10,
    ) -> list[PauseRecord]:
        """Get pause/resume history for a session."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM pause_records
                WHERE session_id IS ?
                ORDER BY initiated_at DESC
                LIMIT ?
                """,
                (str(session_id) if session_id else None, limit),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        return [
            PauseRecord(
                id=UUID(row["id"]),
                state=PauseState(row["state"]),
                initiated_at=datetime.fromisoformat(row["initiated_at"]),
                resumed_at=datetime.fromisoformat(row["resumed_at"]) if row["resumed_at"] else None,
                session_id=UUID(row["session_id"]) if row["session_id"] else None,
                reason=row["reason"] or "",
            )
            for row in rows
        ]

    def is_cac_injection_allowed(self, session_id: UUID | None = None) -> bool:
        """Check if CAC injection is allowed for this session.

        CAC injection is disabled when the session is paused.
        """
        return not self.is_paused(session_id)
