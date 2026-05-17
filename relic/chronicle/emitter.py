"""Chronicle emitter — write-path for events, decisions, snapshots, provenance edges.

Module: relic.chronicle.emitter
Version: chronicle-emitter/v1
Reference: docs/chronicle/agentic-development-plan.md §8.1, T014

Dual-write strategy (§9.bis):
  1. JSONL append FIRST (immutable forensic journal)
  2. SQLite insert SECOND (source of truth for queries)
  If SQLite fails → JSONL already written → chronicle verify --repair can recover.
  If JSONL fails → do NOT write SQLite → fail-open with error code.

All emit functions are fail-open (never block the main runtime path).
"""
from __future__ import annotations

import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from relic.chronicle import context as pctx

# Import schema models
from relic.chronicle.schema import (
    AccessLogEntry,
    Decision,
    Event,
    ProvenanceEdge,
    StateSnapshot,
)

# Import enums
from relic.chronicle.enums import EventCategory, RetentionPolicy, Severity

# Reuse PrivacyLevel from core
from relic.persistence import PrivacyLevel

# Import redaction
from relic.chronicle.redaction import contains_secret, redact_payload

# Import consent gate
from relic.chronicle.consent_gate import is_capture_allowed

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _chronicle_base_dir() -> Path:
    """Return ~/.relic/chronicle/ directory, creating it if needed."""
    base = Path.home() / ".relic" / "chronicle"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _journal_dir() -> Path:
    """Return journal directory for daily JSONL files."""
    d = _chronicle_base_dir() / "journal"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _today_journal_path() -> Path:
    """Return path to today's journal file."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _journal_dir() / f"{today}.jsonl"


# ---------------------------------------------------------------------------
# JSONL writer
# ---------------------------------------------------------------------------

def _write_jsonl_entry(entry: dict[str, Any]) -> bool:
    """Append an entry to today's journal JSONL file.

    Returns True on success, False on failure (fail-open).
    """
    try:
        path = _today_journal_path()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
        return True
    except Exception as e:
        logger.error(f"[chronicle] JSONL write failed: {e}", exc_info=True)
        return False


# ---------------------------------------------------------------------------
# SQLite writer
# ---------------------------------------------------------------------------

def _get_db_connection() -> "sqlite3.Connection":
    """Get the Relic SQLite connection via relic.db."""
    try:
        from relic.db import get_connection
        return get_connection()
    except Exception as e:
        logger.error(f"[chronicle] Failed to get DB connection: {e}")
        raise


def _insert_row(table: str, row: dict[str, Any]) -> bool:
    """Insert a row into a Chronicle table.

    Uses INSERT OR ABORT — Chronicle audit log is immutable (plan §5.1).
    UUID collision is statistically impossible; if it happens, that is a bug
    worth surfacing, not a silent overwrite. Returns False on collision so
    caller can react (chronicle verify --repair).
    """
    conn = None
    try:
        conn = _get_db_connection()
        cols = list(row.keys())
        placeholders = ", ".join(["?"] * len(cols))
        values = [row[c] for c in cols]
        sql = f"INSERT OR ABORT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        conn.execute(sql, values)
        conn.commit()
        return True
    except Exception as e:
        import sqlite3 as _sqlite
        if isinstance(e, _sqlite.IntegrityError):
            logger.error(
                f"[chronicle] PRIMARY KEY collision in {table} (immutability violated): {e}"
            )
        else:
            logger.error(f"[chronicle] SQLite insert failed for {table}: {e}", exc_info=True)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return False


# ---------------------------------------------------------------------------
# Core emit functions
# ---------------------------------------------------------------------------

def _get_context_ids(event: Event) -> None:
    """Populate trace_id, run_id, session_id, experiment_id from contextvars."""
    if event.trace_id is None:
        ctx = pctx.get_trace_id()
        if ctx:
            event.trace_id = ctx
    if event.run_id is None:
        ctx = pctx.get_run_id()
        if ctx:
            event.run_id = ctx
    if event.session_id is None:
        ctx = pctx.get_session_id()
        if ctx:
            event.session_id = ctx
    if event.experiment_id is None:
        ctx = pctx.get_experiment_id()
        if ctx:
            event.experiment_id = ctx


def _compute_payload_hash(payload: dict[str, Any]) -> str:
    """Compute sha256:<hex> hash of payload for deduplication.

    Uses relic.artifacts.checksums.compute_checksum which accepts dict directly
    and serializes it canonically (sort_keys=True). Passing bytes here would
    trigger str(bytes) coercion and produce a hash of the Python repr — a bug.
    """
    from relic.artifacts.checksums import compute_checksum
    digest = compute_checksum(payload).lower()
    return f"sha256:{digest}"


def emit_event(
    *,
    event_type: str,
    event_category: EventCategory | str,
    source_module: str,
    payload: dict[str, Any] | None = None,
    sensitivity: PrivacyLevel | str = PrivacyLevel.SAFE,
    consent_basis: str | None = None,
    parent_event_id: uuid.UUID | None = None,
    severity: str = "info",
    trace_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    experiment_id: uuid.UUID | None = None,
    subject_id: str | None = None,
    agent_id: str | None = None,
    profile_id: str | None = None,
    hermes_profile_id: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    source: str | None = None,
    target_module: str | None = None,
    duration_ms: float | None = None,
    input_refs: list[str] | None = None,
    output_refs: list[str] | None = None,
    tags: list[str] | None = None,
    error_code: str | None = None,
    retry_count: int = 0,
    retention_policy: RetentionPolicy | str = RetentionPolicy.STANDARD_365D,
    **extra_kwargs: Any,
) -> uuid.UUID:
    """Emit one Chronicle event.

    Returns event_id (UUID). Fail-open: if emission fails, logs error and
    returns a dummy UUID (all zeros) so the caller never blocks.

    Args:
        event_type: snake_case event type (e.g., 'model_called', 'memory_write')
        event_category: EventCategory enum value or string
        source_module: dotted module path of the emitter (e.g., 'relic.gumi.llm_narrator')
        payload: event payload (will be redacted, never raw content)
        sensitivity: PrivacyLevel (default SAFE)
        consent_basis: ConsentType string for capture-time gate
        parent_event_id: parent span for hierarchical traces
        severity: debug/info/warning/error/critical

    The trace_id, run_id, session_id, experiment_id are automatically
    populated from the current contextvars if not provided.
    """
    # Normalize event_category
    if isinstance(event_category, str):
        try:
            event_category = EventCategory(event_category)
        except ValueError:
            event_category = EventCategory.BACKGROUND

    # Normalize sensitivity
    if isinstance(sensitivity, str):
        try:
            sensitivity = PrivacyLevel(sensitivity)
        except ValueError:
            sensitivity = PrivacyLevel.SAFE

    # Normalize retention_policy
    if isinstance(retention_policy, str):
        try:
            retention_policy = RetentionPolicy(retention_policy)
        except ValueError:
            retention_policy = RetentionPolicy.STANDARD_365D

    # Build event object — fail-open on validation errors
    payload = payload or {}
    trace_id = trace_id or pctx.get_trace_id() or uuid.uuid4()

    try:
        event = Event(
            event_type=event_type,
            event_category=event_category,
            source_module=source_module,
            payload=payload,
            sensitivity=sensitivity,
            consent_basis=consent_basis,
            parent_event_id=parent_event_id,
            severity=severity,
            trace_id=trace_id,
            run_id=run_id,
            session_id=session_id,
            experiment_id=experiment_id,
            subject_id=subject_id,
            agent_id=agent_id,
            profile_id=profile_id,
            hermes_profile_id=hermes_profile_id,
            actor_type=actor_type,
            actor_id=actor_id,
            target_module=target_module,
            duration_ms=duration_ms,
            input_refs=input_refs or [],
            output_refs=output_refs or [],
            tags=tags or [],
            error_code=error_code,
            retry_count=retry_count,
            retention_policy=retention_policy,
        )
    except Exception as exc:
        logger.error(
            f"[chronicle] emit_event Pydantic validation failed for type={event_type!r} "
            f"in {source_module}: {exc}"
        )
        return uuid.UUID("00000000-0000-0000-0000-000000000000")

    # Apply context
    _get_context_ids(event)

    # Consent gate
    try:
        consent_type_val = consent_basis
        if consent_type_val is not None:
            allowed, reason = is_capture_allowed(consent_type_val, event.subject_id, event.session_id)
            if not allowed:
                logger.warning(f"[chronicle] emit_event blocked by consent: {reason}")
                return uuid.UUID("00000000-0000-0000-0000-000000000000")
    except Exception as e:
        logger.warning(f"[chronicle] consent_gate error: {e} — proceeding anyway")

    # Secret redaction
    try:
        if contains_secret(payload):
            event.payload_redacted = True
            event.payload = redact_payload(payload)
    except Exception as e:
        logger.warning(f"[chronicle] redaction error: {e} — proceeding with original payload")

    # Compute payload hash
    try:
        event.payload_hash = _compute_payload_hash(event.payload)
    except Exception:
        pass  # non-critical

    # Dual-write: JSONL FIRST
    try:
        jsonl_row = event.to_db_row()
        jsonl_ok = _write_jsonl_entry(jsonl_row)
    except Exception as e:
        logger.error(f"[chronicle] JSONL write failed: {e}", exc_info=True)
        jsonl_ok = False

    # SQLite SECOND (only if JSONL succeeded)
    if jsonl_ok:
        try:
            row = event.to_db_row()
            _insert_row("chronicle_events", row)
        except Exception as e:
            logger.error(f"[chronicle] SQLite insert failed: {e} — JSONL already written, will be recovered by verify", exc_info=True)
    else:
        # JSONL failed → do NOT write SQLite (fail-open)
        logger.error(
            f"[chronicle] emit_event failed for {event_type} in {source_module} — "
            f"JSONL write failed, SQLite not attempted. trace_id={event.trace_id}",
            exc_info=True,
        )

    return event.event_id


def emit_decision(
    *,
    decision_kind: str,
    selected_action: dict[str, Any],
    actor_type: str,
    actor_id: str,
    observable_inputs: dict[str, Any] | None = None,
    rejected_alternatives: list[dict[str, Any]] | None = None,
    rationale_summary: str = "",
    confidence: float | None = None,
    evidence_refs: list[str] | None = None,
    trace_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    subject_id: str | None = None,
    consent_basis: str | None = None,
    sensitivity: PrivacyLevel | str = PrivacyLevel.SAFE,
    **kwargs: Any,
) -> uuid.UUID:
    """Emit one decision record.

    Returns decision_id. Fail-open.
    """
    if isinstance(sensitivity, str):
        try:
            sensitivity = PrivacyLevel(sensitivity)
        except ValueError:
            sensitivity = PrivacyLevel.SAFE

    trace_id = trace_id or pctx.get_trace_id() or uuid.uuid4()

    try:
        decision = Decision(
            decision_kind=decision_kind,
            selected_action=selected_action,
            actor_type=actor_type,
            actor_id=actor_id,
            observable_inputs=observable_inputs or {},
            rejected_alternatives=rejected_alternatives or [],
            rationale_summary=rationale_summary[:280] if rationale_summary else None,
            confidence=confidence,
            evidence_refs=evidence_refs or [],
            trace_id=trace_id,
            run_id=run_id,
            session_id=session_id,
            subject_id=subject_id,
            consent_basis=consent_basis,
            sensitivity=sensitivity,
            **kwargs,
        )
    except Exception as exc:
        logger.error(
            f"[chronicle] emit_decision validation failed for kind={decision_kind!r}: {exc}"
        )
        return uuid.UUID("00000000-0000-0000-0000-000000000000")

    # Consent gate
    if consent_basis:
        try:
            allowed, reason = is_capture_allowed(consent_basis, subject_id, session_id)
            if not allowed:
                logger.warning(f"[chronicle] emit_decision blocked by consent: {reason}")
                return uuid.UUID("00000000-0000-0000-0000-000000000000")
        except Exception as e:
            logger.warning(f"[chronicle] consent_gate error: {e}")

    # Dual-write
    try:
        jsonl_row = decision.to_db_row()
        jsonl_ok = _write_jsonl_entry(jsonl_row)
    except Exception as e:
        logger.error(f"[chronicle] decision JSONL write failed: {e}")
        jsonl_ok = False

    if jsonl_ok:
        try:
            _insert_row("chronicle_decisions", decision.to_db_row())
        except Exception as e:
            logger.error(f"[chronicle] decision SQLite insert failed: {e}")

    return decision.decision_id


def emit_snapshot(
    *,
    snapshot_type: str,
    subject_id: str | None,
    scope_ref: str,
    content: dict[str, Any] | str | bytes,
    trigger_event_id: uuid.UUID | None = None,
    previous_snapshot_id: uuid.UUID | None = None,
    sensitivity: PrivacyLevel | str = PrivacyLevel.SAFE,
    retention_policy: RetentionPolicy | str = RetentionPolicy.STANDARD_365D,
    trace_id: uuid.UUID | None = None,
    content_ref: str | None = None,
    **kwargs: Any,
) -> uuid.UUID:
    """Capture state snapshot.

    content is hashed. For large content, content_ref points to artifact/blob.
    Returns snapshot_id. Fail-open.
    """
    if isinstance(sensitivity, str):
        try:
            sensitivity = PrivacyLevel(sensitivity)
        except ValueError:
            sensitivity = PrivacyLevel.SAFE

    if isinstance(retention_policy, str):
        try:
            retention_policy = RetentionPolicy(retention_policy)
        except ValueError:
            retention_policy = RetentionPolicy.STANDARD_365D

    # Compute content hash
    if isinstance(content, dict):
        import hashlib
        raw = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
        content_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        if content_ref is None:
            content_ref = f"inline:{len(raw)}b"
        content_size = len(raw)
    elif isinstance(content, str):
        import hashlib
        raw = content.encode("utf-8")
        content_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        if content_ref is None:
            content_ref = "inline:string"
        content_size = len(raw)
    else:
        import hashlib
        raw = bytes(content)
        content_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        if content_ref is None:
            content_ref = "inline:bytes"
        content_size = len(raw)

    trace_id = trace_id or pctx.get_trace_id() or uuid.uuid4()

    snapshot = StateSnapshot(
        snapshot_type=snapshot_type,
        subject_id=subject_id,
        scope_ref=scope_ref,
        trace_id=trace_id,
        content_hash=content_hash,
        content_ref=content_ref,
        content_size_bytes=content_size,
        trigger_event_id=trigger_event_id,
        previous_snapshot_id=previous_snapshot_id,
        sensitivity=sensitivity,
        retention_policy=retention_policy,
        **kwargs,
    )

    # Dual-write
    try:
        jsonl_row = snapshot.to_db_row()
        jsonl_ok = _write_jsonl_entry(jsonl_row)
    except Exception as e:
        logger.error(f"[chronicle] snapshot JSONL write failed: {e}")
        jsonl_ok = False

    if jsonl_ok:
        try:
            _insert_row("chronicle_state_snapshots", snapshot.to_db_row())
        except Exception as e:
            logger.error(f"[chronicle] snapshot SQLite insert failed: {e}")

    return snapshot.snapshot_id


def emit_provenance_edge(
    *,
    artifact_id: uuid.UUID,
    from_node_type: str,
    from_node_id: uuid.UUID,
    relation: str,
    contribution_role: str | None = None,
    weight: float = 1.0,
    trace_id: uuid.UUID | None = None,
    **kwargs: Any,
) -> uuid.UUID:
    """Add an edge to artifact provenance graph.

    Returns edge_id. Fail-open.
    """
    from relic.chronicle.enums import ProximityOrder

    try:
        relation_enum = ProximityOrder(relation)
    except ValueError:
        relation_enum = ProximityOrder.USED

    trace_id = trace_id or pctx.get_trace_id() or uuid.uuid4()

    edge = ProvenanceEdge(
        artifact_id=artifact_id,
        from_node_type=from_node_type,
        from_node_id=from_node_id,
        relation=relation_enum,
        contribution_role=contribution_role,
        weight=weight,
        trace_id=trace_id,
        **kwargs,
    )

    # Dual-write
    try:
        jsonl_row = edge.to_db_row()
        jsonl_ok = _write_jsonl_entry(jsonl_row)
    except Exception as e:
        logger.error(f"[chronicle] provenance edge JSONL write failed: {e}")
        jsonl_ok = False

    if jsonl_ok:
        try:
            _insert_row("chronicle_provenance_edges", edge.to_db_row())
        except Exception as e:
            logger.error(f"[chronicle] provenance edge SQLite insert failed: {e}")

    return edge.edge_id


# ---------------------------------------------------------------------------
# Span context manager
# ---------------------------------------------------------------------------

from contextlib import contextmanager
from typing import Generator


@contextmanager
def start_span(
    op: str,
    *,
    event_category: EventCategory | str = EventCategory.BACKGROUND,
    source_module: str | None = None,
    tags: list[str] | None = None,
    trace_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    subject_id: str | None = None,
    **kwargs: Any,
) -> Generator[uuid.UUID, None, None]:
    """Context manager: emit START event on entry, COMPLETE/FAIL event on exit.

    Usage:
        with start_span("model_call", source_module="relic.gumi.llm_narrator",
                        event_category=EventCategory.MODEL) as span_id:
            # do work
            pass  # emits COMPLETE

    Returns the span_id (UUID). Raises original exception after emitting FAIL event.
    Sets parent_event_id automatically.
    """
    import time

    if isinstance(event_category, str):
        try:
            event_category = EventCategory(event_category)
        except ValueError:
            event_category = EventCategory.BACKGROUND

    start_time = time.time()
    start_trace_id = trace_id or pctx.get_trace_id()
    parent = pctx.get_span_id()

    # Generate new span_id
    span_id = uuid.uuid4()
    pctx.set_span_id(span_id)

    start_event_id: uuid.UUID | None = None

    try:
        # Emit START
        start_event_id = emit_event(
            event_type=f"{op}_start",
            event_category=event_category,
            source_module=source_module or "relic.chronicle",
            trace_id=start_trace_id,
            run_id=run_id or pctx.get_run_id(),
            session_id=session_id or pctx.get_session_id(),
            subject_id=subject_id,
            parent_event_id=parent,
            severity="debug",
            tags=tags or [],
            input_refs=[f"span:{span_id}"],
            **kwargs,
        )

        yield span_id

        # Emit COMPLETE
        duration_ms = (time.time() - start_time) * 1000
        emit_event(
            event_type=f"{op}_complete",
            event_category=event_category,
            source_module=source_module or "relic.chronicle",
            trace_id=start_trace_id,
            run_id=run_id or pctx.get_run_id(),
            session_id=session_id or pctx.get_session_id(),
            subject_id=subject_id,
            parent_event_id=span_id,
            duration_ms=duration_ms,
            severity="debug",
            tags=tags or [],
            output_refs=[f"event:{start_event_id}"],
            **kwargs,
        )

    except Exception as exc:
        # Emit FAIL
        duration_ms = (time.time() - start_time) * 1000
        try:
            emit_event(
                event_type=f"{op}_fail",
                event_category=EventCategory.ERROR,
                source_module=source_module or "relic.chronicle",
                trace_id=start_trace_id,
                run_id=run_id or pctx.get_run_id(),
                session_id=session_id or pctx.get_session_id(),
                subject_id=subject_id,
                parent_event_id=span_id,
                duration_ms=duration_ms,
                severity="error",
                tags=tags or [],
                error_code=type(exc).__name__,
                **kwargs,
            )
        except Exception:
            pass  # never block on emit failure
        raise
    finally:
        # Reset span_id
        pctx.set_span_id(parent if parent else None)  # type: ignore
