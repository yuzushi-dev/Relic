"""Chronicle access audit, records every researcher/researcher-mode access.

Module: relic.chronicle.access_audit
Version: chronicle-access/v1
Reference: docs/chronicle/agentic-development-plan.md §6.5, T023

Every query/timeline/export/delete call via Chronicle CLI must be logged here
before returning data to the researcher.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from relic.chronicle.schema import AccessLogEntry

logger = logging.getLogger(__name__)


def _compute_result_hash(data: Any) -> str:
    """Compute deterministic hash of result for audit."""
    import json
    try:
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]
    except Exception:
        return "hash_error"


def log_access(
    *,
    accessor_id: str,
    access_kind: str,
    target_filter: dict[str, Any] | None = None,
    rows_returned: int = 0,
    result_data: Any | None = None,
    reason: str | None = None,
    trace_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> uuid.UUID:
    """Log a Chronicle access event to `chronicle_access_log`.

    Returns access_id. Fail-open (never blocks the access operation).

    Args:
        accessor_id: researcher identifier, e.g. "researcher:cristina" or "system"
        access_kind: query/timeline/decision/snapshot/provenance/export/delete/reaper_run/replay/report/config_change/forensic_mode/encryption_key_access
        target_filter: filter applied (e.g., {"subject_id": "X", "category": "memory"})
        rows_returned: number of rows returned by the access
        result_data: the actual data returned (for hashing, never stored raw)
        reason: why this access was made (optional, free-text)
        trace_id: associated trace
        ip_address: client IP (from request context if available)
        user_agent: client user agent
    """
    from relic.chronicle.enums import AccessKind

    try:
        kind_enum = AccessKind(access_kind)
    except ValueError:
        kind_enum = AccessKind.QUERY  # safe fallback

    target_filter = target_filter or {}

    # Compute result hash for integrity verification
    result_hash: str | None = None
    if result_data is not None:
        try:
            result_hash = _compute_result_hash(result_data)
        except Exception:
            pass

    # Build entry
    entry = AccessLogEntry(
        accessor_id=accessor_id,
        access_kind=kind_enum,
        target_filter=target_filter,
        rows_returned=rows_returned,
        result_hash=result_hash,
        reason=reason,
        trace_id=trace_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Write to DB via dual-write
    try:
        from relic.chronicle.emitter import _write_jsonl_entry, _insert_row

        jsonl_row = entry.to_db_row()
        jsonl_ok = _write_jsonl_entry(jsonl_row)

        if jsonl_ok:
            try:
                _insert_row("chronicle_access_log", entry.to_db_row())
            except Exception as e:
                logger.error(f"[chronicle.access_audit] SQLite insert failed: {e}")
        else:
            logger.warning(f"[chronicle.access_audit] JSONL write failed, access not logged")
    except Exception as e:
        logger.error(f"[chronicle.access_audit] log_access failed: {e}", exc_info=True)
        # Fail-open: don't block the access operation

    return entry.access_id


def log_query(
    *,
    accessor_id: str,
    filters: dict[str, Any],
    rows_returned: int,
    trace_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Convenience: log a `query` access."""
    return log_access(
        accessor_id=accessor_id,
        access_kind="query",
        target_filter=filters,
        rows_returned=rows_returned,
        trace_id=trace_id,
    )


def log_export(
    *,
    accessor_id: str,
    subject_id: str,
    format: str = "tar",
    bytes_written: int = 0,
    trace_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Convenience: log an `export` access."""
    return log_access(
        accessor_id=accessor_id,
        access_kind="export",
        target_filter={"subject_id": subject_id, "format": format},
        rows_returned=bytes_written,
        trace_id=trace_id,
    )


def log_delete(
    *,
    accessor_id: str,
    subject_id: str,
    rows_deleted: int = 0,
    cascade: bool = False,
    trace_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Convenience: log a `delete` access."""
    return log_access(
        accessor_id=accessor_id,
        access_kind="delete",
        target_filter={"subject_id": subject_id, "cascade": cascade},
        rows_returned=rows_deleted,
        trace_id=trace_id,
    )
