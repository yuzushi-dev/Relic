"""Consent management for user control over data processing."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from relic.db import get_connection


class ConsentType(str, Enum):
    """Types of consent."""
    MEMORY_STORAGE = "memory_storage"
    ANALYTICS = "analytics"
    ROLEPLAY = "roleplay"
    DATA_SHARING = "data_sharing"


class ConsentScope(str, Enum):
    """Scopes of consent."""
    SESSION = "session"
    SESSION_WITHIN_APP = "session_within_app"
    PERMANENT = "permanent"


class ConsentDecision(BaseModel):
    """A consent decision record."""
    id: UUID = Field(default_factory=uuid4)
    consent_type: ConsentType
    scope: ConsentScope
    granted: bool
    granted_at: datetime = Field(default_factory=datetime.utcnow)
    session_id: UUID | None = None
    expires_at: datetime | None = None
    reason: str = ""


class ConsentManager:
    """Manages user consent for various data processing operations."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def record_consent(
        self,
        consent_type: ConsentType,
        scope: ConsentScope,
        granted: bool,
        session_id: UUID | None = None,
        reason: str = "",
    ) -> ConsentDecision:
        """Record a consent decision."""
        decision = ConsentDecision(
            consent_type=consent_type,
            scope=scope,
            granted=granted,
            session_id=session_id,
            reason=reason,
        )

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO consent_records
                (id, session_id, consent_type, granted, scope, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(decision.id),
                    str(session_id) if session_id else None,
                    consent_type.value,
                    granted,
                    scope.value,
                    decision.granted_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return decision

    def check_consent(
        self,
        consent_type: ConsentType,
        session_id: UUID | None = None,
    ) -> bool:
        """Check if consent exists and is currently valid."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT granted, scope, expires_at
                FROM consent_records
                WHERE consent_type = ? AND session_id IS ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (consent_type.value, str(session_id) if session_id else None),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return False

        granted = row["granted"]
        scope = row["scope"]
        expires_at = row["expires_at"]

        if not granted:
            return False

        if scope == ConsentScope.SESSION.value:
            return True

        if expires_at:
            expires = datetime.fromisoformat(expires_at)
            if datetime.utcnow() > expires:
                return False

        return True

    def revoke_consent(
        self,
        consent_type: ConsentType,
        session_id: UUID | None = None,
    ) -> bool:
        """Revoke previously granted consent."""
        return self.record_consent(
            consent_type=consent_type,
            scope=ConsentScope.SESSION,
            granted=False,
            session_id=session_id,
            reason="user_revoked",
        ).granted is False

    def list_active_consents(
        self,
        session_id: UUID | None = None,
    ) -> list[ConsentDecision]:
        """List all active consent decisions for a session."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM consent_records
                WHERE session_id IS ?
                ORDER BY created_at DESC
                """,
                (str(session_id) if session_id else None,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        return [
            ConsentDecision(
                id=UUID(row["id"]),
                consent_type=ConsentType(row["consent_type"]),
                scope=ConsentScope(row["scope"]),
                granted=row["granted"],
                granted_at=datetime.fromisoformat(row["created_at"]),
                session_id=UUID(row["session_id"]) if row["session_id"] else None,
                reason="",
            )
            for row in rows
        ]
