"""Chronicle legacy JSONL adapter — migrate 7 legacy JSONL files to Chronicle SQLite.

Module: relic.chronicle.adapters.legacy_jsonl
Version: chronicle-legacy/v1
Reference: docs/chronicle/agentic-development-plan.md §14.2, T024

Migrates:
  1. ~/.relic/decision_events.jsonl       → chronicle_events (event_type="cron_decision_legacy")
  2. ~/.relic/cac_trace.jsonl             → chronicle_events (event_type="cac_trace_recorded")
  3. ~/.relic/privacy_trace.jsonl         → chronicle_events (event_type="privacy_decision")
     (handles BOTH Opzione A and Opzione B formats — see T002)
  4. ~/.relic/escalation_log.jsonl        → chronicle_events (event_type="safety_escalation")
  5. ~/.relic/subjects/<id>/bootstrap_session.jsonl → chronicle_events (event_type="bootstrap_step_state")
  6. ~/.relic/subjects/<id>/profile_edit_log.jsonl   → chronicle_events (event_type="profile_edit_legacy")
  7. ~/.relic/subjects/<id>/delivery_decision_log.jsonl → chronicle_decisions (decision_kind="delivery_decision")

Idempotency: skip rows where (timestamp, source_module, payload_hash) already exists.
Dual-write: after migration, producers continue writing both legacy + Chronicle for 3 minor releases.

IMPORTANT: PrivacyTrace schema conflict (T002):
  - Opzione A (privacy/trace.py): has decision/category/confidence/redacted/rehydration_blocked/final_output_blocked
  - Opzione B (persistence.py): has trace_id/stage/content_hash/privacy_level/policy_applied
  - Both written to ~/.relic/privacy_trace.jsonl. Migration detects format by presence of "decision" field.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(data: dict) -> str:
    """Compute payload_hash for idempotency check."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _get_db_connection():
    try:
        from relic.db import get_connection
        return get_connection()
    except Exception as e:
        logger.error(f"[chronicle.legacy] DB unavailable: {e}")
        raise


def _already_migrated(payload_hash: str, conn) -> bool:
    """Check if a row with this payload_hash already exists."""
    row = conn.execute(
        "SELECT 1 FROM chronicle_events WHERE payload_hash = ? LIMIT 1",
        (payload_hash,),
    ).fetchone()
    return row is not None


def _insert_event(row: dict, conn) -> None:
    """Insert event row into chronicle_events."""
    cols = list(row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT OR IGNORE INTO chronicle_events ({', '.join(cols)}) VALUES ({placeholders})"
    values = [row[c] for c in cols]
    conn.execute(sql, values)


def _insert_decision(row: dict, conn) -> None:
    """Insert decision row into chronicle_decisions."""
    cols = list(row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT OR IGNORE INTO chronicle_decisions ({', '.join(cols)}) VALUES ({placeholders})"
    values = [row[c] for c in cols]
    conn.execute(sql, values)


def _read_jsonl(path: Path) -> list[dict]:
    """Read all lines from a JSONL file."""
    if not path.exists():
        return []
    lines = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning(f"[chronicle.legacy] invalid JSON line in {path}: {line[:80]}")
    except Exception as e:
        logger.error(f"[chronicle.legacy] failed to read {path}: {e}")
    return lines


def _default_event(row: dict, event_type: str, source_module: str) -> dict:
    """Build default chronicle_events row."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_category": "background",
        "trace_id": str(uuid.uuid4()),
        "source_module": source_module,
        "timestamp": row.get("timestamp") or row.get("created_at") or _utc_now(),
        "payload": json.dumps(row, sort_keys=True),
        "payload_hash": _compute_hash(row),
        "sensitivity": "safe",
        "visibility": "researcher",
        "retention_policy": "standard_365d",
        "tags": "[]",
        "severity": "info",
        "schema_version": "chronicle-event/v1",
        "created_at": _utc_now(),
        "input_refs": "[]",
        "output_refs": "[]",
    }


# ---------------------------------------------------------------------------
# Individual migrators
# ---------------------------------------------------------------------------

def migrate_decision_events(
    path: Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Migrate ~/.relic/decision_events.jsonl → chronicle_events.

    Original schema: {timestamp, decision, action, confidence, rationale, rejected}
    """
    path = path or (Path.home() / ".relic" / "decision_events.jsonl")
    results = {"path": str(path), "total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    rows = _read_jsonl(path)
    results["total"] = len(rows)
    if not rows:
        return results

    conn = _get_db_connection()

    for row in rows:
        try:
            payload = {
                "decision": row.get("decision", ""),
                "action": row.get("action", row.get("selected_action", "")),
                "confidence": row.get("confidence"),
                "rationale": row.get("rationale", ""),
                "rejected": row.get("rejected", []),
                "timestamp": row.get("timestamp", ""),
            }
            p_hash = _compute_hash(payload)
            if not dry_run and _already_migrated(p_hash, conn):
                results["skipped"] += 1
                continue

            event_row = _default_event(row, "cron_decision_legacy", "relic.gumi_plugin.cron_wiring")
            event_row["payload"] = json.dumps(payload, sort_keys=True)
            event_row["payload_hash"] = p_hash
            event_row["timestamp"] = row.get("timestamp", _utc_now())

            if not dry_run:
                _insert_event(event_row, conn)
            results["migrated"] += 1
        except Exception as e:
            logger.error(f"[chronicle.legacy] decision_events: {e}")
            results["errors"] += 1

    if not dry_run:
        conn.commit()
    return results


def migrate_cac_trace(
    path: Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Migrate ~/.relic/cac_trace.jsonl → chronicle_events.

    Original schema: {timestamp, prompt_hash, admission, score, profile_ref}
    """
    path = path or (Path.home() / ".relic" / "cac_trace.jsonl")
    results = {"path": str(path), "total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    rows = _read_jsonl(path)
    results["total"] = len(rows)
    if not rows:
        return results

    conn = _get_db_connection()

    for row in rows:
        try:
            payload = {
                "prompt_hash": row.get("prompt_hash", ""),
                "admission": row.get("admission", ""),
                "score": row.get("score"),
                "profile_ref": row.get("profile_ref", ""),
            }
            p_hash = _compute_hash(payload)
            if not dry_run and _already_migrated(p_hash, conn):
                results["skipped"] += 1
                continue

            event_row = _default_event(row, "cac_trace_recorded", "relic.cac.trace")
            event_row["payload"] = json.dumps(payload, sort_keys=True)
            event_row["payload_hash"] = p_hash
            event_row["event_category"] = "eval"

            if not dry_run:
                _insert_event(event_row, conn)
            results["migrated"] += 1
        except Exception as e:
            logger.error(f"[chronicle.legacy] cac_trace: {e}")
            results["errors"] += 1

    if not dry_run:
        conn.commit()
    return results


def migrate_privacy_trace(
    path: Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Migrate ~/.relic/privacy_trace.jsonl → chronicle_events.

    Handles BOTH Opzione A and Opzione B (see T002).
    Detection: if row has "decision" field → Opzione A. If "stage" field → Opzione B.

    Opzione A mapping (privacy/trace.py):
      decision → payload["gateway_decision"]
      category → payload["content_category"]
      confidence → payload["decision_confidence"]
      redacted → payload["redacted"]
      rehydration_blocked → payload["rehydration_blocked"]
      final_output_blocked → payload["final_output_blocked"]
      privacy_level: infer from flags (S0 if final_output_blocked, S1 if rehydration_blocked, S2 if redacted, SAFE else)

    Opzione B mapping (persistence.py):
      stage → payload["stage"]
      content_hash → payload["content_hash"]
      privacy_level → sensitivity (direct copy)
      policy_applied → payload["policy_applied"]
    """
    path = path or (Path.home() / ".relic" / "privacy_trace.jsonl")
    results = {"path": str(path), "total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    rows = _read_jsonl(path)
    results["total"] = len(rows)
    if not rows:
        return results

    conn = _get_db_connection()

    for row in rows:
        try:
            # Detect format
            is_opzione_a = "decision" in row
            is_opzione_b = "stage" in row

            if is_opzione_a:
                # Opzione A: infer privacy level from flags
                if row.get("final_output_blocked"):
                    sensitivity = "s0_hard_violation"
                elif row.get("rehydration_blocked"):
                    sensitivity = "s1_quarantine"
                elif row.get("redacted"):
                    sensitivity = "s2_warning"
                else:
                    sensitivity = "safe"

                payload = {
                    "gateway_decision": row.get("decision", ""),
                    "content_category": row.get("category"),
                    "decision_confidence": row.get("confidence"),
                    "redacted": row.get("redacted", False),
                    "rehydration_blocked": row.get("rehydration_blocked", False),
                    "final_output_blocked": row.get("final_output_blocked", False),
                    "metadata": row.get("metadata", {}),
                    "source": "opzione_a",  # tag for post-migration audit
                }
            elif is_opzione_b:
                # Opzione B: direct mapping
                pl = row.get("privacy_level", "safe")
                if hasattr(pl, "value"):
                    pl = pl.value
                elif isinstance(pl, dict):
                    pl = pl.get("value", "safe")
                sensitivity = str(pl).lower().replace("_", " ")

                payload = {
                    "stage": row.get("stage", "unknown"),
                    "content_hash": row.get("content_hash", ""),
                    "privacy_level": row.get("privacy_level"),
                    "policy_applied": row.get("policy_applied", "legacy"),
                    "rehydration_context": row.get("rehydration_context"),
                    "source": "opzione_b",
                }
            else:
                # Unknown format — skip
                results["skipped"] += 1
                continue

            p_hash = _compute_hash(payload)
            if not dry_run and _already_migrated(p_hash, conn):
                results["skipped"] += 1
                continue

            event_row = _default_event(row, "privacy_decision", "relic.privacy.trace")
            event_row["payload"] = json.dumps(payload, sort_keys=True)
            event_row["payload_hash"] = p_hash
            event_row["event_category"] = "privacy"
            event_row["sensitivity"] = sensitivity

            if not dry_run:
                _insert_event(event_row, conn)
            results["migrated"] += 1

        except Exception as e:
            logger.error(f"[chronicle.legacy] privacy_trace: {e}")
            results["errors"] += 1

    if not dry_run:
        conn.commit()
    return results


def migrate_escalation_log(
    path: Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Migrate ~/.relic/escalation_log.jsonl → chronicle_events."""
    path = path or (Path.home() / ".relic" / "escalation_log.jsonl")
    results = {"path": str(path), "total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    rows = _read_jsonl(path)
    results["total"] = len(rows)
    if not rows:
        return results

    conn = _get_db_connection()

    for row in rows:
        try:
            payload = {
                "incident_id": row.get("incident_id", ""),
                "severity": row.get("severity", "medium"),
                "subject_id": row.get("subject_id", ""),
                "action": row.get("action", ""),
            }
            p_hash = _compute_hash(payload)
            if not dry_run and _already_migrated(p_hash, conn):
                results["skipped"] += 1
                continue

            event_row = _default_event(row, "safety_escalation", "relic.safety.escalation_notifier")
            event_row["payload"] = json.dumps(payload, sort_keys=True)
            event_row["payload_hash"] = p_hash
            event_row["event_category"] = "safety"
            event_row["severity"] = row.get("severity", "high")
            event_row["subject_id"] = row.get("subject_id")

            if not dry_run:
                _insert_event(event_row, conn)
            results["migrated"] += 1
        except Exception as e:
            logger.error(f"[chronicle.legacy] escalation_log: {e}")
            results["errors"] += 1

    if not dry_run:
        conn.commit()
    return results


def migrate_bootstrap_session(
    subject_id: str,
    path: Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Migrate ~/.relic/subjects/<subject_id>/bootstrap_session.jsonl → chronicle_events."""
    path = path or (Path.home() / ".relic" / "subjects" / subject_id / "bootstrap_session.jsonl")
    results = {"path": str(path), "total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    rows = _read_jsonl(path)
    results["total"] = len(rows)
    if not rows:
        return results

    conn = _get_db_connection()

    for row in rows:
        try:
            payload = {
                "step": row.get("step", row.get("state", "")),
                "state": row.get("state", ""),
                "outcome": row.get("outcome", "unknown"),
            }
            p_hash = _compute_hash(payload)
            if not dry_run and _already_migrated(p_hash, conn):
                results["skipped"] += 1
                continue

            event_row = _default_event(row, "bootstrap_step_state", "relic.profile.bootstrap_tui")
            event_row["payload"] = json.dumps(payload, sort_keys=True)
            event_row["payload_hash"] = p_hash
            event_row["event_category"] = "profile"
            event_row["subject_id"] = subject_id

            if not dry_run:
                _insert_event(event_row, conn)
            results["migrated"] += 1
        except Exception as e:
            logger.error(f"[chronicle.legacy] bootstrap_session: {e}")
            results["errors"] += 1

    if not dry_run:
        conn.commit()
    return results


def migrate_profile_edit_log(
    subject_id: str,
    path: Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Migrate ~/.relic/subjects/<subject_id>/profile_edit_log.jsonl → chronicle_events."""
    path = path or (Path.home() / ".relic" / "subjects" / subject_id / "profile_edit_log.jsonl")
    results = {"path": str(path), "total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    rows = _read_jsonl(path)
    results["total"] = len(rows)
    if not rows:
        return results

    conn = _get_db_connection()

    for row in rows:
        try:
            payload = {
                "before_hash": row.get("before_hash", ""),
                "after_hash": row.get("after_hash", ""),
                "trigger": row.get("trigger", ""),
                "outcome": row.get("outcome", "unknown"),
            }
            p_hash = _compute_hash(payload)
            if not dry_run and _already_migrated(p_hash, conn):
                results["skipped"] += 1
                continue

            event_row = _default_event(row, "profile_edit_legacy", "relic.profile.registry")
            event_row["payload"] = json.dumps(payload, sort_keys=True)
            event_row["payload_hash"] = p_hash
            event_row["event_category"] = "profile"
            event_row["subject_id"] = subject_id

            if not dry_run:
                _insert_event(event_row, conn)
            results["migrated"] += 1
        except Exception as e:
            logger.error(f"[chronicle.legacy] profile_edit_log: {e}")
            results["errors"] += 1

    if not dry_run:
        conn.commit()
    return results


def migrate_delivery_decision_log(
    subject_id: str,
    path: Path | None = None,
    dry_run: bool = True,
) -> dict:
    """Migrate ~/.relic/subjects/<subject_id>/delivery_decision_log.jsonl → chronicle_decisions."""
    path = path or (Path.home() / ".relic" / "subjects" / subject_id / "delivery_decision_log.jsonl")
    results = {"path": str(path), "total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    rows = _read_jsonl(path)
    results["total"] = len(rows)
    if not rows:
        return results

    conn = _get_db_connection()

    for row in rows:
        try:
            selected = row.get("selected_action", row.get("action", {}))
            rejected = row.get("rejected_alternatives", row.get("rejected", []))

            dec_row = {
                "decision_id": str(uuid.uuid4()),
                "trace_id": str(uuid.uuid4()),
                "decision_kind": "delivery_decision",
                "selected_action": json.dumps(selected if isinstance(selected, dict) else {"action": str(selected)}, sort_keys=True),
                "rejected_alternatives": json.dumps(rejected if isinstance(rejected, list) else [], sort_keys=True),
                "rationale_summary": str(row.get("rationale", ""))[:280],
                "timestamp": row.get("timestamp", _utc_now()),
                "subject_id": subject_id,
                "actor_type": "agent",
                "actor_id": "cron_wiring",
                "sensitivity": "safe",
                "validation_status": "pending",
                "evidence_refs": "[]",
                "observable_inputs": "{}",
                "observable_outputs": "{}",
                "schema_version": "chronicle-decision/v1",
                "created_at": _utc_now(),
            }

            p_hash = _compute_hash(dec_row)
            if not dry_run:
                existing = conn.execute(
                    "SELECT 1 FROM chronicle_decisions WHERE decision_id = ?", (dec_row["decision_id"],)
                ).fetchone()
                if existing:
                    results["skipped"] += 1
                    continue

            if not dry_run:
                cols = list(dec_row.keys())
                placeholders = ", ".join(["?"] * len(cols))
                sql = f"INSERT OR IGNORE INTO chronicle_decisions ({', '.join(cols)}) VALUES ({placeholders})"
                conn.execute(sql, [dec_row[c] for c in cols])
            results["migrated"] += 1

        except Exception as e:
            logger.error(f"[chronicle.legacy] delivery_decision_log: {e}")
            results["errors"] += 1

    if not dry_run:
        conn.commit()
    return results


# ---------------------------------------------------------------------------
# Full migration entry point
# ---------------------------------------------------------------------------

def migrate_all(
    subject_ids: list[str] | None = None,
    dry_run: bool = True,
) -> dict:
    """Run all legacy JSONL migrations.

    Args:
        subject_ids: list of subject IDs to migrate (default: discover from ~/.relic/subjects/)
        dry_run: if True, only counts. if False, writes to DB.

    Returns dict with results per migration + summary counts.
    """
    results: dict = {
        "dry_run": dry_run,
        "timestamp": _utc_now(),
        "migrations": {},
        "summary": {},
    }

    # Global files
    global_migrations = [
        ("decision_events", migrate_decision_events, None),
        ("cac_trace", migrate_cac_trace, None),
        ("privacy_trace", migrate_privacy_trace, None),
        ("escalation_log", migrate_escalation_log, None),
    ]

    for name, fn, _ in global_migrations:
        try:
            r = fn(dry_run=dry_run)
            results["migrations"][name] = r
            logger.info(f"[chronicle.legacy] {name}: migrated={r['migrated']}, skipped={r['skipped']}, errors={r['errors']}")
        except Exception as e:
            logger.error(f"[chronicle.legacy] {name} failed: {e}")
            results["migrations"][name] = {"error": str(e)}

    # Subject-specific files
    if subject_ids is None:
        subjects_dir = Path.home() / ".relic" / "subjects"
        if subjects_dir.exists():
            subject_ids = [d.name for d in subjects_dir.iterdir() if d.is_dir()]

    if subject_ids:
        subject_migrations = [
            ("bootstrap_session", migrate_bootstrap_session),
            ("profile_edit_log", migrate_profile_edit_log),
            ("delivery_decision_log", migrate_delivery_decision_log),
        ]

        for subj in subject_ids:
            results["migrations"][f"subject_{subj}"] = {}
            for name, fn in subject_migrations:
                try:
                    r = fn(subject_id=subj, dry_run=dry_run)
                    results["migrations"][f"subject_{subj}"][name] = r
                    logger.info(f"[chronicle.legacy] {subj}/{name}: migrated={r['migrated']}, skipped={r['skipped']}")
                except Exception as e:
                    logger.error(f"[chronicle.legacy] {subj}/{name} failed: {e}")
                    results["migrations"][f"subject_{subj}"][name] = {"error": str(e)}

    # Summary
    total_migrated = sum(
        r.get("migrated", 0)
        for sub in results["migrations"].values()
        for r in (sub.values() if isinstance(sub, dict) else [sub])
        if isinstance(r, dict) and "migrated" in r
    )
    total_skipped = sum(
        r.get("skipped", 0)
        for sub in results["migrations"].values()
        for r in (sub.values() if isinstance(sub, dict) else [sub])
        if isinstance(r, dict) and "skipped" in r
    )
    results["summary"] = {
        "total_migrated": total_migrated,
        "total_skipped": total_skipped,
        "dry_run": dry_run,
    }

    return results
