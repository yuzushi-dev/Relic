"""Chronicle reader, read-path for events, decisions, snapshots, provenance edges.

Module: relic.chronicle.reader
Version: chronicle-reader/v1
Reference: docs/chronicle/agentic-development-plan.md §8.1, T070

All queries read from SQLite source-of-truth. JSONL is never read by the reader.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _get_db_connection():
    try:
        from relic.db import get_connection
        return get_connection()
    except Exception as e:
        logger.error(f"[chronicle.reader] DB unavailable: {e}")
        raise


# ---------------------------------------------------------------------------
# Event queries
# ---------------------------------------------------------------------------

def query_events(
    *,
    trace_id: uuid.UUID | str | None = None,
    session_id: uuid.UUID | str | None = None,
    run_id: uuid.UUID | str | None = None,
    experiment_id: uuid.UUID | str | None = None,
    subject_id: str | None = None,
    event_type: str | None = None,
    event_category: str | None = None,
    sensitivity: str | None = None,
    severity: str | None = None,
    source_module: str | None = None,
    since: str | None = None,  # ISO8601 timestamp
    until: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query chronicle_events with filters. Returns list of row dicts."""
    try:
        conn = _get_db_connection()
    except Exception as e:
        return []

    conditions = ["1=1"]
    params: list[Any] = []

    if trace_id:
        conditions.append("trace_id = ?")
        params.append(str(trace_id))
    if session_id:
        conditions.append("session_id = ?")
        params.append(str(session_id))
    if run_id:
        conditions.append("run_id = ?")
        params.append(str(run_id))
    if experiment_id:
        conditions.append("experiment_id = ?")
        params.append(str(experiment_id))
    if subject_id:
        conditions.append("subject_id = ?")
        params.append(subject_id)
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if event_category:
        conditions.append("event_category = ?")
        params.append(event_category)
    if sensitivity:
        conditions.append("sensitivity = ?")
        params.append(sensitivity)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if source_module:
        conditions.append("source_module LIKE ?")
        params.append(f"{source_module}%")
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)
    if until:
        conditions.append("timestamp <= ?")
        params.append(until)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT event_id, event_type, event_category, trace_id, run_id, session_id,
               parent_event_id, experiment_id, subject_id, agent_id, profile_id,
               hermes_profile_id, actor_type, actor_id, source_module, target_module,
               timestamp, duration_ms, input_refs, output_refs, payload_redacted,
               payload_hash, payload, sensitivity, visibility, consent_basis,
               retention_policy, tags, severity, validation_status, error_code,
               retry_count, schema_version, created_at
        FROM chronicle_events
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    try:
        rows = conn.execute(sql, params).fetchall()
        cols = [
            "event_id", "event_type", "event_category", "trace_id", "run_id", "session_id",
            "parent_event_id", "experiment_id", "subject_id", "agent_id", "profile_id",
            "hermes_profile_id", "actor_type", "actor_id", "source_module", "target_module",
            "timestamp", "duration_ms", "input_refs", "output_refs", "payload_redacted",
            "payload_hash", "payload", "sensitivity", "visibility", "consent_basis",
            "retention_policy", "tags", "severity", "validation_status", "error_code",
            "retry_count", "schema_version", "created_at",
        ]
        return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        logger.error(f"[chronicle.reader] query_events failed: {e}")
        return []


def query_decisions(
    *,
    trace_id: uuid.UUID | str | None = None,
    session_id: uuid.UUID | str | None = None,
    subject_id: str | None = None,
    decision_kind: str | None = None,
    actor_id: str | None = None,
    validation_status: str | None = None,
    since: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query chronicle_decisions with filters."""
    try:
        conn = _get_db_connection()
    except Exception:
        return []

    conditions = ["1=1"]
    params: list[Any] = []

    if trace_id:
        conditions.append("trace_id = ?")
        params.append(str(trace_id))
    if session_id:
        conditions.append("session_id = ?")
        params.append(str(session_id))
    if subject_id:
        conditions.append("subject_id = ?")
        params.append(subject_id)
    if decision_kind:
        conditions.append("decision_kind = ?")
        params.append(decision_kind)
    if actor_id:
        conditions.append("actor_id = ?")
        params.append(actor_id)
    if validation_status:
        conditions.append("validation_status = ?")
        params.append(validation_status)
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT decision_id, trace_id, run_id, session_id, subject_id, actor_type,
               actor_id, decision_kind, selected_action, rejected_alternatives,
               observable_inputs, observable_outputs, confidence, uncertainty_notes,
               evidence_refs, rationale_summary, consent_basis, sensitivity,
               validation_status, timestamp, schema_version, created_at
        FROM chronicle_decisions
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    try:
        cols = [
            "decision_id", "trace_id", "run_id", "session_id", "subject_id", "actor_type",
            "actor_id", "decision_kind", "selected_action", "rejected_alternatives",
            "observable_inputs", "observable_outputs", "confidence", "uncertainty_notes",
            "evidence_refs", "rationale_summary", "consent_basis", "sensitivity",
            "validation_status", "timestamp", "schema_version", "created_at",
        ]
        rows = conn.execute(sql, params).fetchall()
        return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        logger.error(f"[chronicle.reader] query_decisions failed: {e}")
        return []


def query_snapshots(
    *,
    subject_id: str | None = None,
    snapshot_type: str | None = None,
    scope_ref: str | None = None,
    since: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query chronicle_state_snapshots."""
    try:
        conn = _get_db_connection()
    except Exception:
        return []

    conditions = ["1=1"]
    params: list[Any] = []

    if subject_id:
        conditions.append("subject_id = ?")
        params.append(subject_id)
    if snapshot_type:
        conditions.append("snapshot_type = ?")
        params.append(snapshot_type)
    if scope_ref:
        conditions.append("scope_ref = ?")
        params.append(scope_ref)
    if since:
        conditions.append("captured_at >= ?")
        params.append(since)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT snapshot_id, snapshot_type, subject_id, scope_ref, captured_at,
               trigger_event_id, previous_snapshot_id, content_hash, content_ref,
               content_size_bytes, diff_from_previous, sensitivity, retention_policy,
               schema_version, created_at
        FROM chronicle_state_snapshots
        WHERE {where}
        ORDER BY captured_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    try:
        cols = [
            "snapshot_id", "snapshot_type", "subject_id", "scope_ref", "captured_at",
            "trigger_event_id", "previous_snapshot_id", "content_hash", "content_ref",
            "content_size_bytes", "diff_from_previous", "sensitivity", "retention_policy",
            "schema_version", "created_at",
        ]
        rows = conn.execute(sql, params).fetchall()
        return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        logger.error(f"[chronicle.reader] query_snapshots failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Join queries
# ---------------------------------------------------------------------------

def join_trace(
    trace_id: uuid.UUID | str,
    *,
    include_events: bool = True,
    include_decisions: bool = True,
    include_snapshots: bool = False,
) -> dict[str, Any]:
    """Retrieve all records for a given trace_id, grouped by type."""
    trace_id_str = str(trace_id)
    result: dict[str, Any] = {
        "trace_id": trace_id_str,
        "events": [],
        "decisions": [],
        "snapshots": [],
        "stats": {},
    }

    if include_events:
        result["events"] = query_events(trace_id=trace_id_str, limit=1000)

    if include_decisions:
        result["decisions"] = query_decisions(trace_id=trace_id_str, limit=1000)

    if include_snapshots:
        # Find session_id from events to filter snapshots
        session_ids = list(set(e.get("session_id") for e in result["events"] if e.get("session_id")))
        for sid in session_ids:
            snaps = query_snapshots(scope_ref=f"session:{sid}", limit=100)
            result["snapshots"].extend(snaps)

    # Compute stats
    result["stats"] = {
        "events_count": len(result["events"]),
        "decisions_count": len(result["decisions"]),
        "snapshots_count": len(result["snapshots"]),
        "event_types": list(set(e.get("event_type", "") for e in result["events"])),
        "decision_kinds": list(set(d.get("decision_kind", "") for d in result["decisions"])),
        "time_span": {
            "first": (result["events"][-1]["timestamp"] if result["events"] else None),
            "last": (result["events"][0]["timestamp"] if result["events"] else None),
        },
    }

    return result


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def stats(
    *,
    subject_id: str | None = None,
    since: str | None = None,
) -> dict[str, Any]:
    """Compute aggregate statistics for events/decisions."""
    try:
        conn = _get_db_connection()
    except Exception:
        return {}

    base_where = "1=1"
    params: list[Any] = []
    if subject_id:
        base_where += " AND subject_id = ?"
        params.append(subject_id)
    if since:
        base_where += " AND timestamp >= ?"
        params.append(since)

    result: dict[str, Any] = {}

    try:
        # Total events
        row = conn.execute(
            f"SELECT COUNT(*) FROM chronicle_events WHERE {base_where}", params
        ).fetchone()
        result["total_events"] = row[0] if row else 0

        # By event_type
        rows = conn.execute(
            f"SELECT event_type, COUNT(*) as cnt FROM chronicle_events WHERE {base_where} GROUP BY event_type ORDER BY cnt DESC LIMIT 20",
            params
        ).fetchall()
        result["by_event_type"] = [{"type": r[0], "count": r[1]} for r in rows]

        # By severity
        rows = conn.execute(
            f"SELECT severity, COUNT(*) as cnt FROM chronicle_events WHERE {base_where} GROUP BY severity ORDER BY cnt DESC",
            params
        ).fetchall()
        result["by_severity"] = [{"severity": r[0], "count": r[1]} for r in rows]

        # By sensitivity
        rows = conn.execute(
            f"SELECT sensitivity, COUNT(*) as cnt FROM chronicle_events WHERE {base_where} GROUP BY sensitivity ORDER BY cnt DESC",
            params
        ).fetchall()
        result["by_sensitivity"] = [{"sensitivity": r[0], "count": r[1]} for r in rows]

        # Total decisions
        p2 = list(params)
        row = conn.execute(
            f"SELECT COUNT(*) FROM chronicle_decisions WHERE {base_where}", p2
        ).fetchone()
        result["total_decisions"] = row[0] if row else 0

        # Total snapshots
        snap_where = base_where.replace("timestamp", "captured_at")
        p3 = list(params)
        row = conn.execute(
            f"SELECT COUNT(*) FROM chronicle_state_snapshots WHERE {snap_where}", p3
        ).fetchone()
        result["total_snapshots"] = row[0] if row else 0

    except Exception as e:
        logger.error(f"[chronicle.reader] stats failed: {e}")

    return result
