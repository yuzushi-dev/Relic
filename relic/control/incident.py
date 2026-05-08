"""Incident reporting for security and privacy events.

This module provides incident tracking with artifact quarantine
linking for proper audit trail.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from relic.db import get_connection


class IncidentSeverity(str, Enum):
    """Severity levels for incidents."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Status of incident investigation."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    QUARANTINED = "quarantined"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class QuarantinedArtifact(BaseModel):
    """An artifact in quarantine."""
    id: UUID
    artifact_type: str
    artifact_hash: str
    quarantined_at: datetime
    reason: str
    session_id: UUID | None = None


class IncidentReport(BaseModel):
    """An incident report record."""
    id: UUID = Field(default_factory=uuid4)
    severity: IncidentSeverity
    status: IncidentStatus
    title: str
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    session_id: UUID | None = None
    quarantined_artifacts: list[QuarantinedArtifact] = Field(default_factory=list)
    related_incident_ids: list[UUID] = Field(default_factory=list)
    metadata_json: str = "{}"


class IncidentReporter:
    """Manages security and privacy incident reporting.

    Incidents are tracked with proper quarantine linking
    to affected artifacts for audit trail.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def create_incident(
        self,
        severity: IncidentSeverity,
        title: str,
        description: str,
        session_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> IncidentReport:
        """Create a new incident report."""
        incident = IncidentReport(
            severity=severity,
            status=IncidentStatus.OPEN,
            title=title,
            description=description,
            session_id=session_id,
            metadata_json=json.dumps(metadata or {}),
        )

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO incident_reports
                (id, severity, status, title, description, created_at, updated_at,
                 session_id, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(incident.id),
                    incident.severity.value,
                    incident.status.value,
                    incident.title,
                    incident.description,
                    incident.created_at.isoformat(),
                    incident.updated_at.isoformat(),
                    str(session_id) if session_id else None,
                    incident.metadata_json,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return incident

    def quarantine_artifact(
        self,
        incident_id: UUID,
        artifact_id: UUID,
        artifact_type: str,
        artifact_hash: str,
        reason: str,
        session_id: UUID | None = None,
    ) -> QuarantinedArtifact:
        """Quarantine an artifact and link it to an incident."""
        quarantine = QuarantinedArtifact(
            id=artifact_id,
            artifact_type=artifact_type,
            artifact_hash=artifact_hash,
            quarantined_at=datetime.utcnow(),
            reason=reason,
            session_id=session_id,
        )

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO quarantined_artifacts
                (id, incident_id, artifact_type, artifact_hash, quarantined_at,
                 reason, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(quarantine.id),
                    str(incident_id),
                    quarantine.artifact_type,
                    quarantine.artifact_hash,
                    quarantine.quarantined_at.isoformat(),
                    quarantine.reason,
                    str(session_id) if session_id else None,
                ),
            )

            cur.execute(
                """
                UPDATE incident_reports
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (IncidentStatus.QUARANTINED.value, datetime.utcnow().isoformat(), str(incident_id)),
            )
            conn.commit()
        finally:
            conn.close()

        return quarantine

    def update_status(
        self,
        incident_id: UUID,
        status: IncidentStatus,
    ) -> IncidentReport:
        """Update the status of an incident."""
        now = datetime.utcnow()

        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE incident_reports
                SET status = ?, updated_at = ?, resolved_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    now.isoformat(),
                    now.isoformat() if status in (IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE) else None,
                    str(incident_id),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return self.get_incident(incident_id)

    def get_incident(
        self,
        incident_id: UUID,
    ) -> IncidentReport:
        """Get an incident by ID with quarantined artifacts."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM incident_reports WHERE id = ?",
                (str(incident_id),),
            )
            row = cur.fetchone()

            cur.execute(
                "SELECT * FROM quarantined_artifacts WHERE incident_id = ?",
                (str(incident_id),),
            )
            quarantine_rows = cur.fetchall()
        finally:
            conn.close()

        if not row:
            raise ValueError(f"Incident not found: {incident_id}")

        quarantined = [
            QuarantinedArtifact(
                id=UUID(r["id"]),
                artifact_type=r["artifact_type"],
                artifact_hash=r["artifact_hash"],
                quarantined_at=datetime.fromisoformat(r["quarantined_at"]),
                reason=r["reason"],
                session_id=UUID(r["session_id"]) if r["session_id"] else None,
            )
            for r in quarantine_rows
        ]

        return IncidentReport(
            id=UUID(row["id"]),
            severity=IncidentSeverity(row["severity"]),
            status=IncidentStatus(row["status"]),
            title=row["title"],
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            session_id=UUID(row["session_id"]) if row["session_id"] else None,
            quarantined_artifacts=quarantined,
            metadata_json=row["metadata_json"] or "{}",
        )

    def list_incidents(
        self,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        limit: int = 100,
    ) -> list[IncidentReport]:
        """List incidents with optional filtering."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            query = "SELECT * FROM incident_reports WHERE 1=1"
            params: list = []

            if status:
                query += " AND status = ?"
                params.append(status.value)

            if severity:
                query += " AND severity = ?"
                params.append(severity.value)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()
        finally:
            conn.close()

        return [
            IncidentReport(
                id=UUID(row["id"]),
                severity=IncidentSeverity(row["severity"]),
                status=IncidentStatus(row["status"]),
                title=row["title"],
                description=row["description"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
                session_id=UUID(row["session_id"]) if row["session_id"] else None,
                quarantined_artifacts=[],
                metadata_json=row["metadata_json"] or "{}",
            )
            for row in rows
        ]

    def generate_report(
        self,
        incident_id: UUID,
        output_path: Path,
    ) -> Path:
        """Generate a detailed incident report to a file."""
        incident = self.get_incident(incident_id)

        report_lines = [
            f"# Incident Report: {incident.title}",
            "",
            f"**ID:** {incident.id}",
            f"**Severity:** {incident.severity.value}",
            f"**Status:** {incident.status.value}",
            f"**Created:** {incident.created_at.isoformat()}",
            f"**Updated:** {incident.updated_at.isoformat()}",
            "",
            "## Description",
            incident.description,
            "",
        ]

        if incident.quarantined_artifacts:
            report_lines.extend([
                "## Quarantined Artifacts",
                "",
            ])
            for artifact in incident.quarantined_artifacts:
                report_lines.extend([
                    f"- **Artifact ID:** {artifact.id}",
                    f"  - **Type:** {artifact.artifact_type}",
                    f"  - **Hash:** {artifact.artifact_hash}",
                    f"  - **Quarantined:** {artifact.quarantined_at.isoformat()}",
                    f"  - **Reason:** {artifact.reason}",
                    "",
                ])

        output_path.write_text("\n".join(report_lines))
        return output_path
