"""Chronicle retention, reaper logic for expired events/snapshots/edges.

Module: relic.chronicle.retention
Version: chronicle-retention/v1
Reference: docs/chronicle/agentic-development-plan.md §14.2, T022

Reaper policy (§9.bis):
  - EPHEMERAL: deleted after 1h
  - SHORT_30D: deleted after 30 days
  - STANDARD_365D: deleted after 365 days
  - EXTENDED_RESEARCH: never auto-delete
  - LEGAL_HOLD: never auto-delete

Reaper NEVER removes JSONL (append-only). Instead:
  1. Archival: daily JSONL → ~/.relic/chronicle/archive/YYYY-MM.tar.gz
  2. Deletion: only SQLite rows + orphan blobs
  3. Subject deletion (GDPR): rewrites JSONL files without subject rows (exception to append-only)
"""
from __future__ import annotations

import gzip
import logging
import os
import shutil
import tarfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from relic.chronicle.enums import RetentionPolicy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time thresholds
# ---------------------------------------------------------------------------

_RETENTION_THRESHOLDS: dict[str, timedelta | None] = {
    "ephemeral": timedelta(hours=1),
    "short_30d": timedelta(days=30),
    "standard_365d": timedelta(days=365),
    "extended_research": None,  # never
    "legal_hold": None,  # never
}


def _threshold(policy: str) -> datetime | None:
    """Return cutoff datetime for a retention policy, or None if never."""
    td = _RETENTION_THRESHOLDS.get(policy)
    if td is None:
        return None
    return datetime.now(timezone.utc) - td


# ---------------------------------------------------------------------------
# Archive daily journal
# ---------------------------------------------------------------------------

def archive_journal(*, dry_run: bool = True) -> dict[str, Any]:
    """Archive today's journal JSONL to tar.gz.

    Args:
        dry_run: if True, returns counts without writing. if False, writes archive.

    Returns dict with keys: journal_size_bytes, archive_path, lines_count, archived.
    """
    from relic.chronicle.emitter import _today_journal_path, _journal_dir

    journal_path = _today_journal_path()
    results: dict[str, Any] = {
        "journal_path": str(journal_path),
        "journal_size_bytes": 0,
        "lines_count": 0,
        "archived": False,
        "archive_path": None,
    }

    if not journal_path.exists():
        return results

    size = journal_path.stat().st_size
    results["journal_size_bytes"] = size

    # Count lines
    try:
        with open(journal_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        results["lines_count"] = len(lines)
    except Exception:
        results["lines_count"] = 0

    if dry_run:
        return results

    # Create archive
    archive_dir = _journal_dir().parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m")
    archive_path = archive_dir / f"{today}.tar.gz"

    try:
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(journal_path, arcname=journal_path.name)
        results["archived"] = True
        results["archive_path"] = str(archive_path)
        logger.info(f"[chronicle.reaper] archived {journal_path.name} → {archive_path}")
    except Exception as e:
        logger.error(f"[chronicle.reaper] archive failed: {e}")

    return results


# ---------------------------------------------------------------------------
# Delete expired records
# ---------------------------------------------------------------------------

def _get_db_connection():
    try:
        from relic.db import get_connection
        return get_connection()
    except Exception as e:
        logger.error(f"[chronicle] DB unavailable: {e}")
        raise


def delete_expired(
    *,
    dry_run: bool = True,
    policy: str | None = None,
    subject_id: str | None = None,
) -> dict[str, Any]:
    """Delete expired events/snapshots from SQLite.

    Args:
        dry_run: if True, returns counts. if False, deletes.
        policy: filter by RetentionPolicy value (default: all deletable)
        subject_id: if provided, only delete for this subject (GDPR deletion path)

    Returns dict with counts per table.
    """
    try:
        conn = _get_db_connection()
    except Exception as e:
        return {"error": str(e)}

    results: dict[str, Any] = {
        "dry_run": dry_run,
        "policy": policy,
        "subject_id": subject_id,
        "chronicle_events_deleted": 0,
        "chronicle_decisions_deleted": 0,
        "chronicle_state_snapshots_deleted": 0,
        "chronicle_provenance_edges_deleted": 0,
        "orphan_blobs_deleted": 0,
    }

    # Build WHERE clause for retention policy
    deletable_policies = ["ephemeral", "short_30d", "standard_365d"]
    if policy:
        if policy not in deletable_policies:
            return results  # nothing to delete for non-deletable policy
        deletable_policies = [policy]

    # Compute cutoff for each policy
    cutoffs = {}
    for pol in deletable_policies:
        cutoff = _threshold(pol)
        if cutoff:
            cutoffs[pol] = cutoff.isoformat()

    if not cutoffs:
        return results  # all policies are non-deletable

    # Build condition. Param ORDER MATTERS: must match placeholder order in WHERE.
    subject_clause = " AND subject_id = ?" if subject_id else ""

    def _delete_table(table: str, where_clause: str, params_list: list) -> int:
        """Delete from table and return count."""
        if dry_run:
            try:
                c = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_clause}", params_list)
                return c.fetchone()[0]
            except Exception:
                return 0
        else:
            try:
                cur = conn.execute(f"DELETE FROM {table} WHERE {where_clause}", params_list)
                conn.commit()
                return cur.rowcount
            except Exception as e:
                logger.error(f"[chronicle.reaper] delete from {table}: {e}")
                return 0

    # Events: placeholder order: retention_policy, timestamp, [subject_id]
    for pol, cutoff in cutoffs.items():
        p = [pol, cutoff] + ([subject_id] if subject_id else [])
        count = _delete_table("chronicle_events", "retention_policy = ? AND timestamp < ?" + subject_clause, p)
        results["chronicle_events_deleted"] += count

    # Decisions
    for pol, cutoff in cutoffs.items():
        p = [pol, cutoff] + ([subject_id] if subject_id else [])
        count = _delete_table("chronicle_decisions", "retention_policy = ? AND timestamp < ?" + subject_clause, p)
        results["chronicle_decisions_deleted"] += count

    # Snapshots: note captured_at instead of timestamp
    for pol, cutoff in cutoffs.items():
        p = [pol, cutoff] + ([subject_id] if subject_id else [])
        count = _delete_table("chronicle_state_snapshots", "retention_policy = ? AND captured_at < ?" + subject_clause, p)
        results["chronicle_state_snapshots_deleted"] += count

    # Provenance edges (orphan after event deletion)
    if subject_id and not dry_run:
        # Only delete orphaned edges (edges where the artifact no longer exists)
        try:
            cur = conn.execute(
                """
                DELETE FROM chronicle_provenance_edges
                WHERE artifact_id NOT IN (SELECT id FROM artifact_records)
                AND from_node_id NOT IN (SELECT event_id FROM chronicle_events)
                """
            )
            conn.commit()
            results["chronicle_provenance_edges_deleted"] = cur.rowcount
        except Exception as e:
            logger.error(f"[chronicle.reaper] orphan edge delete: {e}")

    return results


# ---------------------------------------------------------------------------
# Reaper run (main entry point)
# ---------------------------------------------------------------------------

def run(
    *,
    dry_run: bool = True,
    policy: str | None = None,
    subject_id: str | None = None,
    archive_journals: bool = True,
) -> dict[str, Any]:
    """Run reaper: archive journals + delete expired records.

    This is the main entry point for `chronicle reaper`.
    """
    results: dict[str, Any] = {
        "dry_run": dry_run,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Archive
    if archive_journals:
        results["archive"] = archive_journal(dry_run=dry_run)

    # Delete
    results["deletion"] = delete_expired(
        dry_run=dry_run,
        policy=policy,
        subject_id=subject_id,
    )

    total = (
        results["deletion"].get("chronicle_events_deleted", 0)
        + results["deletion"].get("chronicle_decisions_deleted", 0)
        + results["deletion"].get("chronicle_state_snapshots_deleted", 0)
        + results["deletion"].get("chronicle_provenance_edges_deleted", 0)
    )
    results["total_deleted"] = total
    results["summary"] = f"dry_run={dry_run}: {total} records"

    logger.info(f"[chronicle.reaper] {'DRY-RUN ' if dry_run else ''}{results['summary']}")

    return results


# ---------------------------------------------------------------------------
# GDPR Art. 17: subject hard delete
# ---------------------------------------------------------------------------

def _rewrite_jsonl_without_subject(path: Path, subject_id: str) -> int:
    """Rewrite JSONL file removing lines where subject_id matches.

    Atomic: writes to a temp file then replaces original.
    Returns count of removed lines (0 = nothing matched, file untouched).
    """
    import json
    import tempfile

    removed = 0
    try:
        with path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()

        kept: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                kept.append(line)
                continue
            try:
                obj = json.loads(stripped)
                if obj.get("subject_id") == subject_id:
                    removed += 1
                    continue
            except json.JSONDecodeError:
                pass  # malformed line, keep it, not our data
            kept.append(line)

        if removed > 0:
            tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".gdpr_purge_")
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                    fh.writelines(kept)
                os.replace(tmp_name, str(path))
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
    except Exception as exc:
        logger.warning(f"[chronicle.purge] JSONL rewrite failed {path}: {exc}")

    return removed


def purge_subject_records(
    subject_id: str,
    *,
    relic_home: Path | None = None,
    cascade: bool = False,
) -> dict[str, Any]:
    """GDPR Art. 17 hard delete, remove ALL chronicle records for subject_id.

    Covers:
    - SQLite tables: chronicle_events, chronicle_decisions,
      chronicle_state_snapshots, chronicle_access_log
      (provenance_edges has no subject_id column, skipped)
    - Daily JSONL journal files under chronicle/journal/
    - Legacy JSONL files at relic_home level

    Warning: irreversible. No dry-run. Callers must confirm before invoking.
    """
    from relic.paths import get_relic_home as _get_relic_home
    home = relic_home or _get_relic_home()

    results: dict[str, Any] = {
        "subject_id": subject_id,
        "chronicle_events_deleted": 0,
        "chronicle_decisions_deleted": 0,
        "chronicle_state_snapshots_deleted": 0,
        "chronicle_access_log_deleted": 0,
        "chronicle_provenance_edges_deleted": 0,
        "journal_files_rewritten": 0,
        "journal_lines_removed": 0,
        "legacy_jsonl_lines_removed": 0,
    }

    # 1. Delete SQLite chronicle rows
    try:
        conn = _get_db_connection()
        if cascade:
            try:
                cur = conn.execute(
                    """
                    DELETE FROM chronicle_provenance_edges
                    WHERE from_node_id IN (
                        SELECT event_id FROM chronicle_events WHERE subject_id = ?
                    )
                    OR trace_id IN (
                        SELECT trace_id FROM chronicle_events WHERE subject_id = ?
                        UNION
                        SELECT trace_id FROM chronicle_decisions WHERE subject_id = ?
                        UNION
                        SELECT trace_id FROM chronicle_state_snapshots WHERE subject_id = ?
                    )
                    """,
                    (subject_id, subject_id, subject_id, subject_id),
                )
                results["chronicle_provenance_edges_deleted"] = cur.rowcount
            except Exception as exc:
                logger.warning(f"[chronicle.purge] provenance cascade failed: {exc}")
        for table, key in [
            ("chronicle_events", "chronicle_events_deleted"),
            ("chronicle_decisions", "chronicle_decisions_deleted"),
            ("chronicle_state_snapshots", "chronicle_state_snapshots_deleted"),
        ]:
            try:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE subject_id = ?", (subject_id,)  # noqa: S608
                )
                results[key] = cur.rowcount
            except Exception as exc:
                logger.warning(f"[chronicle.purge] {table} delete failed: {exc}")
        try:
            cur = conn.execute(
                "DELETE FROM chronicle_access_log WHERE target_filter LIKE ?",
                (f'%"{subject_id}"%',),
            )
            results["chronicle_access_log_deleted"] = cur.rowcount
        except Exception as exc:
            logger.warning(f"[chronicle.purge] chronicle_access_log delete failed: {exc}")
        conn.commit()
    except Exception as exc:
        logger.error(f"[chronicle.purge] DB connection failed: {exc}")
        results["db_error"] = str(exc)

    # 2. Rewrite daily JSONL journals
    journal_dir = home / "chronicle" / "journal"
    if journal_dir.exists():
        for journal_path in sorted(journal_dir.glob("*.jsonl")):
            removed = _rewrite_jsonl_without_subject(journal_path, subject_id)
            if removed > 0:
                results["journal_files_rewritten"] += 1
                results["journal_lines_removed"] += removed

    # 3. Filter legacy JSONL files at relic_home level
    legacy_total = 0
    for fname in (
        "decision_events.jsonl",
        "cac_trace.jsonl",
        "privacy_trace.jsonl",
        "escalation_log.jsonl",
    ):
        p = home / fname
        if p.exists():
            legacy_total += _rewrite_jsonl_without_subject(p, subject_id)
    results["legacy_jsonl_lines_removed"] = legacy_total

    logger.info(
        "[chronicle.purge] subject=%s deleted events=%d decisions=%d snapshots=%d "
        "access=%d journal_lines=%d legacy_lines=%d",
        subject_id,
        results["chronicle_events_deleted"],
        results["chronicle_decisions_deleted"],
        results["chronicle_state_snapshots_deleted"],
        results["chronicle_access_log_deleted"],
        results["journal_lines_removed"],
        results["legacy_jsonl_lines_removed"],
    )
    return results
