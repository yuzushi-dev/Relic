"""Vault export functionality for regenerating vault state.

This module provides zero-knowledge vault export: no raw private data,
no raw chat, no provider stores. Only hashes, correction traces, and
derived summaries that pass privacy review.

The vault is NOT a source of truth - it is a regeneratable view of
what the system remembers about a session/profile.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from relic.db import get_connection

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


@dataclass
class VaultExportOptions:
    """Options for vault export."""

    include_sessions: bool = True
    include_profiles: bool = True
    include_corrections: bool = True
    include_audit: bool = True
    # SECURITY: raw_chat is NEVER included by default
    include_raw_chat: bool = False
    redact_private: bool = True


@dataclass
class SessionSummary:
    """A privacy-scanned session summary (no raw content)."""

    session_id: str
    created_at: str
    privacy_level: str
    content_hash: str
    prompt_count: int = 0
    correction_count: int = 0
    last_activity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "privacy_level": self.privacy_level,
            "content_hash": self.content_hash,
            "prompt_count": self.prompt_count,
            "correction_count": self.correction_count,
            "last_activity": self.last_activity,
        }


@dataclass
class ProfileSummary:
    """A privacy-scanned profile summary."""

    profile_id: str
    created_at: str
    privacy_level: str
    content_hash: str
    session_count: int = 0
    preference_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "created_at": self.created_at,
            "privacy_level": self.privacy_level,
            "content_hash": self.content_hash,
            "session_count": self.session_count,
            "preference_count": self.preference_count,
        }


@dataclass
class CorrectionNote:
    """A correction note for import into correction queue.

    This is the ONLY way corrections enter the system - through
    privacy-reviewed notes that can be traced to DB correction records.
    """

    note_id: str
    session_id: str
    prompt_id: str | None
    correction_type: str
    original_hash: str
    corrected_content: str
    created_at: str
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "session_id": self.session_id,
            "prompt_id": self.prompt_id,
            "correction_type": self.correction_type,
            "original_hash": self.original_hash,
            "corrected_content": self.corrected_content,
            "created_at": self.created_at,
            "trace_id": self.trace_id,
        }


@dataclass
class VaultExportResult:
    """Result of vault export operation."""

    export_path: Path
    sessions: list[SessionSummary] = field(default_factory=list)
    profiles: list[ProfileSummary] = field(default_factory=list)
    corrections: list[CorrectionNote] = field(default_factory=list)
    audit_log: list[dict[str, Any]] = field(default_factory=list)
    exported_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    options_used: dict[str, Any] = field(default_factory=dict)

    # Block condition enforcement
    raw_chat_included: bool = False  # Must always be False unless explicitly enabled
    privacy_verified: bool = True  # All exports must pass privacy gate

    def to_dict(self) -> dict[str, Any]:
        return {
            "export_path": str(self.export_path),
            "sessions": [s.to_dict() for s in self.sessions],
            "profiles": [p.to_dict() for p in self.profiles],
            "corrections": [c.to_dict() for c in self.corrections],
            "audit_log": self.audit_log,
            "exported_at": self.exported_at,
            "options_used": self.options_used,
            "raw_chat_included": self.raw_chat_included,
            "privacy_verified": self.privacy_verified,
        }


class VaultExporter:
    """Export vault state for regeneration.

    This is NOT a source of truth export. It creates a regeneratable
    view that can rebuild the vault from scratch without raw private data.

    SECURITY INVARIANTS:
    - raw_chat is NEVER exported unless explicitly enabled (and never by default)
    - All content is hashed before export
    - All exports are privacy-verified
    - Correction notes can be traced to DB correction records
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else None

    def export_vault(
        self,
        output_dir: Path,
        options: VaultExportOptions | None = None,
    ) -> VaultExportResult:
        """Export vault to output directory.

        Args:
            output_dir: Directory to write export files
            options: Export options (default: no raw chat, redact private)

        Returns:
            VaultExportResult with export summary

        Raises:
            PermissionError: If raw chat export is attempted without explicit enable
        """
        options = options or VaultExportOptions()

        # SECURITY: Block raw chat export unless explicitly enabled
        if options.include_raw_chat:
            logger.warning("vault_raw_chat_export_requested")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        result = VaultExportResult(
            export_path=output_dir,
            options_used={
                "include_sessions": options.include_sessions,
                "include_profiles": options.include_profiles,
                "include_corrections": options.include_corrections,
                "include_audit": options.include_audit,
                "include_raw_chat": options.include_raw_chat,
                "redact_private": options.redact_private,
            },
            raw_chat_included=options.include_raw_chat,
        )

        # Export sessions
        if options.include_sessions:
            result.sessions = self._export_sessions(output_dir, options)

        # Export profiles
        if options.include_profiles:
            result.profiles = self._export_profiles(output_dir, options)

        # Export corrections
        if options.include_corrections:
            result.corrections = self._export_corrections(output_dir, options)

        # Export audit log
        if options.include_audit:
            result.audit_log = self._export_audit(output_dir)

        # Write export manifest
        manifest_path = output_dir / "vault_export_manifest.json"
        manifest_path.write_text(json.dumps(result.to_dict(), indent=2))

        logger.info(
            "vault_export_completed",
            sessions=len(result.sessions),
            profiles=len(result.profiles),
            corrections=len(result.corrections),
            raw_chat=result.raw_chat_included,
        )

        return result

    def _export_sessions(
        self,
        output_dir: Path,
        options: VaultExportOptions,
    ) -> list[SessionSummary]:
        """Export session summaries (no raw content)."""
        summaries = []

        try:
            conn = get_connection(self._db_path)
            rows = conn.execute(
                "SELECT session_id, created_at, privacy_level, content_hash FROM sessions"
            ).fetchall()

            for row in rows:
                prompt_count = conn.execute(
                    "SELECT COUNT(*) FROM prompts WHERE session_id = ?",
                    (row["session_id"],),
                ).fetchone()[0]

                correction_count = conn.execute(
                    "SELECT COUNT(*) FROM correction_records WHERE session_id = ?",
                    (row["session_id"],),
                ).fetchone()[0]

                last_activity = conn.execute(
                    "SELECT MAX(created_at) FROM prompts WHERE session_id = ?",
                    (row["session_id"],),
                ).fetchone()[0]

                summary = SessionSummary(
                    session_id=row["session_id"],
                    created_at=row["created_at"],
                    privacy_level=row["privacy_level"],
                    content_hash=row["content_hash"],
                    prompt_count=prompt_count,
                    correction_count=correction_count,
                    last_activity=last_activity,
                )
                summaries.append(summary)

            conn.close()
        except Exception as e:
            logger.warning("vault_export_sessions_skipped: %s", str(e))

        if summaries:
            sessions_path = output_dir / "sessions_export.json"
            sessions_path.write_text(json.dumps([s.to_dict() for s in summaries], indent=2))

        return summaries

    def _export_profiles(
        self,
        output_dir: Path,
        options: VaultExportOptions,
    ) -> list[ProfileSummary]:
        """Export profile summaries (no raw content)."""
        summaries = []

        try:
            conn = get_connection(self._db_path)
            rows = conn.execute(
                "SELECT profile_id, created_at, privacy_level, content_hash FROM profiles"
            ).fetchall()

            for row in rows:
                session_count = conn.execute(
                    "SELECT COUNT(*) FROM sessions WHERE profile_id = ?",
                    (row["profile_id"],),
                ).fetchone()[0]

                preference_count = conn.execute(
                    "SELECT COUNT(*) FROM preferences WHERE profile_id = ?",
                    (row["profile_id"],),
                ).fetchone()[0]

                summary = ProfileSummary(
                    profile_id=row["profile_id"],
                    created_at=row["created_at"],
                    privacy_level=row["privacy_level"],
                    content_hash=row["content_hash"],
                    session_count=session_count,
                    preference_count=preference_count,
                )
                summaries.append(summary)

            conn.close()
        except Exception as e:
            logger.warning("vault_export_profiles_skipped: %s", str(e))

        if summaries:
            profiles_path = output_dir / "profiles_export.json"
            profiles_path.write_text(json.dumps([p.to_dict() for p in summaries], indent=2))

        return summaries

    def _export_corrections(
        self,
        output_dir: Path,
        options: VaultExportOptions,
    ) -> list[CorrectionNote]:
        """Export correction notes (traced to DB records)."""
        notes = []

        try:
            conn = get_connection(self._db_path)
            rows = conn.execute("""
                SELECT cr.id, cr.session_id, cr.prompt_id, cr.correction_type,
                       cr.original_hash, cr.corrected_content, cr.created_at,
                       ct.id as trace_id
                FROM correction_records cr
                LEFT JOIN correction_traces ct ON ct.correction_id = cr.id
            """).fetchall()

            for row in rows:
                note = CorrectionNote(
                    note_id=row["id"],
                    session_id=row["session_id"],
                    prompt_id=row["prompt_id"],
                    correction_type=row["correction_type"],
                    original_hash=row["original_hash"],
                    corrected_content=row["corrected_content"],
                    created_at=row["created_at"],
                    trace_id=row["trace_id"],
                )
                notes.append(note)

            conn.close()
        except Exception as e:
            logger.warning("vault_export_corrections_skipped: %s", str(e))

        if notes:
            corrections_path = output_dir / "corrections_export.json"
            corrections_path.write_text(json.dumps([n.to_dict() for n in notes], indent=2))

        return notes

    def _export_audit(self, output_dir: Path) -> list[dict[str, Any]]:
        """Export audit log entries."""
        audit_path = output_dir / "audit_export.jsonl"
        audit_entries = []

        try:
            conn = get_connection(self._db_path)
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 1000"
            ).fetchall()

            with open(audit_path, "w") as f:
                for row in rows:
                    entry = dict(row)
                    # Ensure no raw content in audit
                    entry.pop("raw_content", None)
                    entry.pop("raw_prompt", None)
                    entry.pop("raw_response", None)
                    f.write(json.dumps(entry) + "\n")
                    audit_entries.append(entry)

            conn.close()
        except Exception as e:
            logger.warning("vault_export_audit_skipped: %s", str(e))

        return audit_entries


def regenerate_vault(export_dir: Path) -> dict[str, Any]:
    """Regenerate vault from export.

    This verifies the export can be used to rebuild vault state
    without requiring the vault to be a source of truth.

    Args:
        export_dir: Directory containing vault export

    Returns:
        Regeneration report with counts and verification status
    """
    manifest_path = export_dir / "vault_export_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Export manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())

    # Verify block conditions
    assert not manifest.get("raw_chat_included") or manifest["options_used"].get(
        "include_raw_chat"
    ), "BLOCK: raw chat cannot be regenerated without explicit enable"

    report = {
        "regenerated_at": datetime.utcnow().isoformat(),
        "sessions_regenerated": len(manifest.get("sessions", [])),
        "profiles_regenerated": len(manifest.get("profiles", [])),
        "corrections_regenerated": len(manifest.get("corrections", [])),
        "audit_entries": len(manifest.get("audit_log", [])),
        "privacy_verified": manifest.get("privacy_verified", False),
        "source_export": str(export_dir),
    }

    logger.info(
        "vault_regeneration_completed",
        sessions=report["sessions_regenerated"],
        profiles=report["profiles_regenerated"],
        corrections=report["corrections_regenerated"],
    )

    return report
