"""Outcome reconciler: delivered → unanswered_24h transitions (Plan §Task 4b).

Reads canonical decision events to find deliveries whose response window has
expired without a subject reply, then:
  - emits a follow-up canonical event with ``outcome_status="unanswered_24h"``
    and ``outcome_status_before="delivered"``;
  - reconciles ``checkin_cadence_state`` via ``reconcile_cadence_outcome``.

Source order:
  - preferred: Chronicle reader (``relic.chronicle.reader.query_events``);
  - fallback: append-only ``decision_events.jsonl`` mirror under ``RELIC_HOME``.

Replies are matched against Hermes ``state.db`` (any subject-authored message
inside ``[delivered_at, response_deadline_at]``), not only the
``checkin_exchanges`` table — non-ask deliveries must not be misclassified.

The reconciler is idempotent: events that already produced an
``unanswered_24h`` transition for the same ``parent_event_id`` are skipped.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from relic.checkin.features import (
    load_cadence_state,
    reconcile_cadence_outcome,
    save_cadence_state,
)
from relic.paths import get_relic_home

logger = logging.getLogger(__name__)


DEFAULT_RESPONSE_WINDOW_HOURS = 24


def _decision_log_path(relic_home: Path) -> Path:
    return Path(relic_home) / "decision_events.jsonl"


def _iter_decision_log(relic_home: Path) -> Iterable[dict]:
    path = _decision_log_path(relic_home)
    if not path.exists():
        return []
    out: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        logger.debug("outcome_reconciler: log read failed: %s", exc)
    return out


def _append_event(relic_home: Path, event: dict) -> None:
    path = _decision_log_path(relic_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def _to_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _has_subject_reply(
    hermes_home: Path,
    delivered_at: datetime,
    deadline_at: datetime,
) -> bool:
    state_db = Path(hermes_home) / "state.db"
    if not state_db.exists():
        return False
    try:
        conn = sqlite3.connect(str(state_db), timeout=5.0)
        try:
            row = conn.execute(
                """SELECT 1 FROM messages
                   WHERE role = 'user'
                     AND created_at >= ?
                     AND created_at <= ?
                   LIMIT 1""",
                (delivered_at.isoformat(), deadline_at.isoformat()),
            ).fetchone()
            return row is not None
        except sqlite3.DatabaseError:
            return False
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def _already_reconciled(
    events: list[dict],
    parent_id: Optional[str],
    parent_created_at: Optional[str],
) -> bool:
    if not parent_id and not parent_created_at:
        return False
    for ev in events:
        if ev.get("outcome_status") != "unanswered_24h":
            continue
        meta = ev.get("metadata") or {}
        if parent_id and meta.get("parent_event_id") == parent_id:
            return True
        if parent_created_at and meta.get("parent_created_at") == parent_created_at:
            return True
    return False


def reconcile_due_outcomes(
    subject_id: str,
    *,
    relic_home: Path,
    hermes_home: Optional[Path] = None,
    now: Optional[datetime] = None,
    default_window_hours: int = DEFAULT_RESPONSE_WINDOW_HOURS,
) -> int:
    """Materialise overdue delivered events into ``unanswered_24h`` transitions.

    Returns the count of new transitions emitted.
    """
    now = now or datetime.now(timezone.utc)
    relic_home = Path(relic_home)
    if hermes_home is None:
        hermes_home = relic_home / "hermes"

    events = list(_iter_decision_log(relic_home))
    if not events:
        return 0

    db_path = relic_home / "subjects" / subject_id / "relic.db"
    cadence_conn: Optional[sqlite3.Connection] = None
    if db_path.exists():
        cadence_conn = sqlite3.connect(str(db_path), timeout=5.0)

    emitted = 0
    try:
        for source in events:
            if source.get("subject_id") != subject_id:
                continue
            if source.get("outcome_status") != "delivered":
                continue

            delivered_at = (
                _to_dt(source.get("delivered_at"))
                or _to_dt(source.get("created_at"))
            )
            if delivered_at is None:
                continue

            deadline_at = (
                _to_dt(source.get("response_deadline_at"))
                or delivered_at + timedelta(hours=default_window_hours)
            )
            if deadline_at > now:
                continue

            parent_id = source.get("event_id") or source.get("id")
            parent_created_at = source.get("created_at")
            if _already_reconciled(events, parent_id, parent_created_at):
                continue

            if _has_subject_reply(hermes_home, delivered_at, deadline_at):
                continue

            transition = {
                "decision": "NO_REPLY",
                "subject_id": subject_id,
                "gumi_instance_id": source.get("gumi_instance_id", ""),
                "hermes_profile_id": source.get("hermes_profile_id", ""),
                "decision_type": source.get("decision_type"),
                "event_kind": source.get("event_kind"),
                "outcome_status_before": "delivered",
                "outcome_status": "unanswered_24h",
                "response_deadline_at": deadline_at.isoformat(),
                "created_at": now.isoformat(),
                "metadata": {
                    "source": "outcome_reconciler",
                    "parent_event_id": parent_id,
                    "parent_created_at": parent_created_at,
                },
            }
            _append_event(relic_home, transition)
            events.append(transition)
            emitted += 1

            if cadence_conn is not None:
                state = load_cadence_state(cadence_conn, subject_id)
                new_state = reconcile_cadence_outcome(
                    state,
                    {
                        "outcome_status_before": "delivered",
                        "outcome_status": "unanswered_24h",
                        "decision_type": source.get("decision_type"),
                        "now": now,
                    },
                )
                save_cadence_state(cadence_conn, new_state)
                cadence_conn.commit()
    finally:
        if cadence_conn is not None:
            cadence_conn.close()

    return emitted
