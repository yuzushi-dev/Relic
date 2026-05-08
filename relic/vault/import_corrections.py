"""Import correction notes into the correction queue.

This module provides the ONLY pathway for corrections to enter the system:
through privacy-reviewed correction notes that can be traced to DB correction
records. Raw private data is NEVER imported - only hashes and metadata.

SECURITY INVARIANTS:
- Corrections can only enter via privacy-reviewed notes
- Each note must be traceable to a DB correction record
- Raw content is NEVER imported - only hashes
- Import is logged for audit trail
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
class CorrectionImportResult:
    """Result of correction note import."""

    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    trace_ids: list[str] = field(default_factory=list)
    imported_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "imported": self.imported,
            "skipped": self.skipped,
            "errors": self.errors,
            "trace_ids": self.trace_ids,
            "imported_at": self.imported_at,
        }


class CorrectionNoteImporter:
    """Import correction notes into the correction queue.

    This is the ONLY authorized pathway for corrections to enter the system.
    Corrections are traced to DB records for audit purposes.

    SECURITY: Raw content is NEVER imported - only hashes that can
    be verified against the DB records.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else None

    def import_note(
        self,
        note_path: Path,
        dry_run: bool = False,
    ) -> CorrectionImportResult:
        """Import a single correction note into the queue.

        Args:
            note_path: Path to correction note JSON
            dry_run: If True, validate without importing

        Returns:
            CorrectionImportResult with import status
        """
        result = CorrectionImportResult()

        if not note_path.exists():
            result.errors.append(f"Note not found: {note_path}")
            return result

        try:
            note_data = json.loads(note_path.read_text())
        except json.JSONDecodeError as e:
            result.errors.append(f"Invalid JSON in {note_path}: {e}")
            return result

        # Validate required fields
        required = ["note_id", "session_id", "correction_type", "original_hash"]
        missing = [f for f in required if f not in note_data]
        if missing:
            result.errors.append(f"Missing required fields: {missing}")
            return result

        # In dry_run mode, just validate structure without DB verification
        if dry_run:
            result.skipped = 1
            logger.info("correction_note_dry_run", note_id=note_data["note_id"])
            return result

        # For actual import, verify note can be traced to DB
        trace_id = self._verify_db_trace(note_data)
        if not trace_id:
            result.errors.append(
                f"Cannot trace note {note_data['note_id']} to DB correction record"
            )
            return result

        result.trace_ids.append(trace_id)
        result.imported = 1
        self._record_import(note_data, trace_id)
        logger.info(
            "correction_note_imported",
            note_id=note_data["note_id"],
            trace_id=trace_id,
        )

        return result

    def import_from_directory(
        self,
        import_dir: Path,
        dry_run: bool = False,
    ) -> CorrectionImportResult:
        """Import all correction notes from a directory.

        Args:
            import_dir: Directory containing correction note JSON files
            dry_run: If True, validate without importing

        Returns:
            Aggregated CorrectionImportResult
        """
        all_results = CorrectionImportResult()

        if not import_dir.exists():
            all_results.errors.append(f"Import directory not found: {import_dir}")
            return all_results

        note_files = list(import_dir.glob("*.json")) + list(import_dir.glob("*.jsonl"))

        for note_file in note_files:
            result = self.import_note(note_file, dry_run=dry_run)
            all_results.imported += result.imported
            all_results.skipped += result.skipped
            all_results.errors.extend(result.errors)
            all_results.trace_ids.extend(result.trace_ids)

        logger.info(
            "correction_import_batch_complete",
            imported=all_results.imported,
            skipped=all_results.skipped,
            errors=len(all_results.errors),
        )

        return all_results

    def _verify_db_trace(self, note_data: dict[str, Any]) -> str | None:
        """Verify note can be traced to a DB correction record.

        Returns trace_id if verifiable, None otherwise.
        """
        try:
            conn = get_connection(self._db_path)
            try:
                # Look up correction by note_id
                row = conn.execute(
                    """
                    SELECT id, trace_id FROM correction_records cr
                    LEFT JOIN correction_traces ct ON ct.correction_id = cr.id
                    WHERE cr.id = ?
                """,
                    (note_data["note_id"],),
                ).fetchone()

                if row:
                    return row["trace_id"] or row["id"]

                # Fallback: look up by original hash
                if "original_hash" in note_data:
                    row = conn.execute(
                        """
                        SELECT id, trace_id FROM correction_records cr
                        LEFT JOIN correction_traces ct ON ct.correction_id = cr.id
                        WHERE cr.original_hash = ?
                    """,
                        (note_data["original_hash"],),
                    ).fetchone()

                    if row:
                        return row["trace_id"] or row["id"]

                return None
            finally:
                conn.close()
        except Exception as e:
            logger.warning("correction_db_trace_failed: %s", str(e))
            return None

    def _record_import(
        self,
        note_data: dict[str, Any],
        trace_id: str,
    ) -> None:
        """Record the import in the audit log."""
        try:
            conn = get_connection(self._db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO audit_log (
                        id, created_at, event_type, session_id,
                        details, privacy_level
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        f"import_{datetime.utcnow().isoformat()}",
                        datetime.utcnow().isoformat(),
                        "correction_note_import",
                        note_data.get("session_id"),
                        json.dumps(
                            {
                                "note_id": note_data.get("note_id"),
                                "trace_id": trace_id,
                                "correction_type": note_data.get("correction_type"),
                            }
                        ),
                        "safe",
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.warning("correction_import_record_failed: %s", str(e))


def import_correction_note(note_path: Path, dry_run: bool = False) -> dict[str, Any]:
    """Convenience function to import a single correction note.

    Args:
        note_path: Path to correction note JSON
        dry_run: If True, validate without importing

    Returns:
        Import result as dict
    """
    importer = CorrectionNoteImporter()
    result = importer.import_note(note_path, dry_run=dry_run)
    return result.to_dict()


def import_correction_directory(
    import_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Convenience function to import all notes from a directory.

    Args:
        import_dir: Directory containing correction notes
        dry_run: If True, validate without importing

    Returns:
        Aggregated import result as dict
    """
    importer = CorrectionNoteImporter()
    result = importer.import_from_directory(import_dir, dry_run=dry_run)
    return result.to_dict()
