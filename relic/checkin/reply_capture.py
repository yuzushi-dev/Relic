"""Reply capture for checkin exchanges.

Captures the subject's next substantive message as a reply to the most
recent pending checkin exchange, writing it into checkin_exchanges.reply_text.

Gating:
- Message must be substantive (length >= MIN_LEN, not a dismissal token)
- consent_for_active_elicitation must be True in delivery_policy.json
- Exchange must have been asked within REPLY_WINDOW_HOURS and have a facet_id

Used by RelicMemoryProvider.sync_turn() as a specific carve-out from
the "no raw text in Hermes memory" policy: raw text goes only to relic.db
(the subject's own longitudinal store), never to Hermes memory.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from relic.checkin.valence import score_valence

logger = logging.getLogger(__name__)

REPLY_WINDOW_HOURS = 12
_MIN_LEN = 3
_DISMISSAL_TOKENS = frozenset({
    "[silent]", "ok", "k", "sì", "si", "no", "ciao", "ok.",
    "boh", "mah", "meh", "lol", "nada", "non so",
})
_DELIVERED_LOOKBACK = timedelta(hours=REPLY_WINDOW_HOURS)


# Signatures of agent/cron scaffold text that must never be captured as a
# subject reply. Under a no-agent cron, the check-in *delivery* turn passes the
# cron instruction prompt into sync_turn as user_msg; without this guard it was
# stored as the check-in reply, corrupting the row and blocking the subject's
# real answer (WHERE reply_text IS NULL).
_AGENT_PROMPT_MARKERS = (
    "you are running as a scheduled cron job",
    "your final response will be automatically delivered",
    "do not use send_message",
    "sei gumi. il gate mostra",
    "se il gate non inizia con deliver",
)


def _is_agent_scaffold(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _AGENT_PROMPT_MARKERS)


def _is_substantive(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < _MIN_LEN:
        return False
    if stripped.lower().rstrip(".!? ") in _DISMISSAL_TOKENS:
        return False
    if _is_agent_scaffold(stripped):
        return False
    return True


def _iter_decision_log(relic_home: Path) -> list[dict]:
    path = Path(relic_home) / "decision_events.jsonl"
    if not path.exists():
        return []
    events: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        logger.debug("reply_capture: decision log read failed", exc_info=True)
    return events


def _to_dt(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _latest_delivered_decision_type(
    relic_home: Path,
    subject_id: str,
    reply_at: datetime,
    *,
    default_window_hours: int = 24,
) -> Optional[str]:
    latest_type: Optional[str] = None
    latest_delivered_at: Optional[datetime] = None
    earliest = reply_at - _DELIVERED_LOOKBACK

    for event in _iter_decision_log(relic_home):
        if event.get("subject_id") != subject_id:
            continue
        if event.get("outcome_status") != "delivered":
            continue

        delivered_at = _to_dt(event.get("delivered_at")) or _to_dt(event.get("created_at"))
        if delivered_at is None or delivered_at < earliest or delivered_at > reply_at:
            continue

        deadline_at = (
            _to_dt(event.get("response_deadline_at"))
            or delivered_at + timedelta(hours=default_window_hours)
        )
        if reply_at > deadline_at:
            continue

        if latest_delivered_at is None or delivered_at > latest_delivered_at:
            latest_delivered_at = delivered_at
            latest_type = event.get("decision_type")

    return latest_type


def capture_reply_if_pending(
    user_msg: str,
    subject_id: str,
    relic_home: str | None = None,
) -> bool:
    """Capture user_msg as reply to the most recent pending checkin exchange.

    Returns True if captured, False if no pending exchange / not substantive.
    Never raises, all errors are logged at debug level.

    Args:
        user_msg: raw user message text (truncated to 2000 chars when stored)
        subject_id: relic subject identifier
        relic_home: override for RELIC_HOME env / default ~/.relic
    """
    if not _is_substantive(user_msg):
        return False

    relic_home_path = Path(relic_home or Path.home() / ".relic")

    dp_path = relic_home_path / "subjects" / subject_id / "delivery_policy.json"
    if not dp_path.exists():
        return False

    try:
        dp = json.loads(dp_path.read_text(encoding="utf-8"))
        if not dp.get("consent_for_active_elicitation", False):
            return False
    except Exception:
        logger.debug("capture_reply_if_pending: delivery_policy load failed", exc_info=True)
        return False

    db_path = relic_home_path / "subjects" / subject_id / "relic.db"
    if not db_path.exists():
        return False

    try:
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=REPLY_WINDOW_HOURS)).isoformat()
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            row = conn.execute(
                """SELECT id, asked_at FROM checkin_exchanges
                   WHERE reply_text IS NULL
                     AND facet_id IS NOT NULL
                     AND asked_at >= ?
                   ORDER BY asked_at DESC
                   LIMIT 1""",
                (cutoff,),
            ).fetchone()
            if row is None:
                return False

            exchange_id, asked_at_raw = row[0], row[1]
            latency_seconds = _compute_latency_seconds(asked_at_raw, now)
            stored_text = (user_msg[:1999] + "…") if len(user_msg) > 2000 else user_msg
            reply_valence = score_valence(stored_text)
            cur = conn.execute(
                """UPDATE checkin_exchanges
                   SET reply_text = ?,
                       reply_valence = ?,
                       reply_captured_at = ?,
                       response_latency_seconds = ?
                   WHERE id = ? AND reply_text IS NULL""",
                (stored_text, reply_valence, now.isoformat(), latency_seconds, exchange_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return False  # lost the race, another writer filled it first
            _reset_cadence_after_reply(
                conn,
                subject_id,
                now,
                relic_home=relic_home_path,
                reply_valence=reply_valence,
            )
            logger.info(
                "capture_reply_if_pending: captured reply for exchange %d subject=%s",
                exchange_id, subject_id,
            )
            return True
        finally:
            conn.close()
    except Exception:
        logger.warning("capture_reply_if_pending: DB error (non-fatal)", exc_info=True)
        return False


def _compute_latency_seconds(asked_at_raw: str | None, reply_at: datetime) -> int | None:
    """Return integer seconds between asked_at and reply_at, NULL on malformed input."""
    if not asked_at_raw:
        return None
    try:
        asked_at = datetime.fromisoformat(asked_at_raw)
    except (TypeError, ValueError):
        return None
    if asked_at.tzinfo is None:
        return None
    try:
        asked_at = asked_at.astimezone(timezone.utc)
        reply_at_utc = reply_at.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None
    delta = (reply_at_utc - asked_at).total_seconds()
    if delta < 0:
        return None
    return int(delta)


def _reset_cadence_after_reply(
    conn: sqlite3.Connection,
    subject_id: str,
    reply_at: datetime,
    *,
    relic_home: Path | None = None,
    reply_valence: float | None = None,
) -> None:
    """Reset cadence streaks via the reconcile_cadence_outcome contract."""
    try:
        from relic.checkin.features import (
            CadenceState,
            load_cadence_state,
            reconcile_cadence_outcome,
            save_cadence_state,
        )
    except Exception:
        return

    try:
        state: CadenceState = load_cadence_state(conn, subject_id)
        event = {"outcome_status": "answered", "now": reply_at}
        if relic_home is not None:
            decision_type = _latest_delivered_decision_type(relic_home, subject_id, reply_at)
            if decision_type is not None:
                event["decision_type"] = decision_type
                if decision_type == "diegetic":
                    event["reply_valence"] = reply_valence
        new_state = reconcile_cadence_outcome(state, event)
        save_cadence_state(conn, new_state)
        conn.commit()
    except Exception:
        logger.debug("_reset_cadence_after_reply: non-fatal", exc_info=True)
