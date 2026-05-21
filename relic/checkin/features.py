"""Feature assembly + cadence state for the checkin policy layer.

This module is the only place that:
  - reads/writes ``checkin_cadence_state``;
  - persists feature snapshots to ``checkin_features``;
  - normalizes decision-event dicts so older sparse JSONL rows are replayable;
  - assembles a ``CheckinFeatures`` vector from existing tables (Plan §Task 4).

Important contracts:

* ``reconcile_cadence_outcome(state, event)`` event dict shape::

      {
          "outcome_status": str | None,
          "outcome_status_before": str | None,
          "decision_type": str | None,
          "reply_valence": float | None,
          "now": datetime | None,
          "boundary_frequency_cap_per_day": int | None,
      }

  Recognised ``outcome_status`` values:
    - "answered"        → reset streaks and update ``last_reply_at``.
    - "unanswered_24h"  → increment streak (and follow-up streak when applicable);
                           only when transitioning from ``"delivered"``.
    - "silent" / None   → leave cadence untouched (silence does not penalise).
    - "delivered"       → record ``last_delivered_initiative_at`` only.

  ``boundary_frequency_cap_per_day`` sets a hard cap independent of cadence
  and does not reset streaks (cap == subject preference, streak == inferred
  signal — they intentionally coexist).

* ``compute_reach_score(non_response_streak, followup_non_response_streak)``
  follows the spike §9 damping curve: ``0.7 ^ streak``, with the follow-up
  streak counted twice so explicit ignores damp faster than generic ones.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from relic.checkin.policy import CheckinFeatures

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cadence state
# ---------------------------------------------------------------------------


@dataclass
class CadenceState:
    subject_id: str
    non_response_streak: int = 0
    followup_non_response_streak: int = 0
    diegetic_non_response_streak: int = 0
    last_delivered_initiative_at: Optional[datetime] = None
    last_diegetic_delivered_at: Optional[datetime] = None
    last_unanswered_delivery_at: Optional[datetime] = None
    last_reply_at: Optional[datetime] = None
    last_subject_msg_at: Optional[datetime] = None
    last_boundary_at: Optional[datetime] = None
    last_decay_at: Optional[datetime] = None
    frequency_cap_per_day: Optional[int] = None
    diegetic_intensity: Optional[float] = None
    diegetic_frequency: Optional[float] = None
    updated_at: Optional[datetime] = None


_REQUIRED_EVENT_KEYS = (
    "outcome_status",
    "outcome_status_before",
    "decision_type",
    "reply_valence",
    "now",
    "boundary_frequency_cap_per_day",
)


def normalize_decision_event_dict(event: Optional[dict]) -> dict:
    """Return a copy of ``event`` with all reconcile keys present (None default)."""
    out = dict(event or {})
    for key in _REQUIRED_EVENT_KEYS:
        out.setdefault(key, None)
    return out


def _to_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
    return None


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


_CADENCE_COLUMNS = (
    "subject_id",
    "non_response_streak",
    "followup_non_response_streak",
    "diegetic_non_response_streak",
    "last_delivered_initiative_at",
    "last_diegetic_delivered_at",
    "last_unanswered_delivery_at",
    "last_reply_at",
    "last_subject_msg_at",
    "last_boundary_at",
    "last_decay_at",
    "frequency_cap_per_day",
    "diegetic_intensity",
    "diegetic_frequency",
    "updated_at",
)


def _cadence_table_columns(conn: sqlite3.Connection) -> set[str]:
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(checkin_cadence_state)").fetchall()}
    except sqlite3.OperationalError:
        return set()


def _cadence_select_expr(column: str, available: set[str]) -> str:
    if column in available:
        return column
    if column == "diegetic_non_response_streak":
        return f"0 AS {column}"
    if column in {
        "last_diegetic_delivered_at",
        "diegetic_intensity",
        "diegetic_frequency",
    }:
        return f"NULL AS {column}"
    return column


def _cadence_values(state: CadenceState, now: datetime) -> dict[str, Any]:
    return {
        "subject_id": state.subject_id,
        "non_response_streak": int(state.non_response_streak),
        "followup_non_response_streak": int(state.followup_non_response_streak),
        "diegetic_non_response_streak": int(state.diegetic_non_response_streak),
        "last_delivered_initiative_at": _to_iso(state.last_delivered_initiative_at),
        "last_diegetic_delivered_at": _to_iso(state.last_diegetic_delivered_at),
        "last_unanswered_delivery_at": _to_iso(state.last_unanswered_delivery_at),
        "last_reply_at": _to_iso(state.last_reply_at),
        "last_subject_msg_at": _to_iso(state.last_subject_msg_at),
        "last_boundary_at": _to_iso(state.last_boundary_at),
        "last_decay_at": _to_iso(state.last_decay_at),
        "frequency_cap_per_day": state.frequency_cap_per_day,
        "diegetic_intensity": state.diegetic_intensity,
        "diegetic_frequency": state.diegetic_frequency,
        "updated_at": _to_iso(now),
    }


def load_cadence_state(conn: sqlite3.Connection, subject_id: str) -> CadenceState:
    available = _cadence_table_columns(conn)
    select_columns = [_cadence_select_expr(column, available) for column in _CADENCE_COLUMNS]
    row = conn.execute(
        f"SELECT {', '.join(select_columns)} FROM checkin_cadence_state WHERE subject_id = ?",
        (subject_id,),
    ).fetchone()
    if row is None:
        return CadenceState(subject_id=subject_id)
    return CadenceState(
        subject_id=row[0],
        non_response_streak=row[1] or 0,
        followup_non_response_streak=row[2] or 0,
        diegetic_non_response_streak=row[3] or 0,
        last_delivered_initiative_at=_to_dt(row[4]),
        last_diegetic_delivered_at=_to_dt(row[5]),
        last_unanswered_delivery_at=_to_dt(row[6]),
        last_reply_at=_to_dt(row[7]),
        last_subject_msg_at=_to_dt(row[8]),
        last_boundary_at=_to_dt(row[9]),
        last_decay_at=_to_dt(row[10]),
        frequency_cap_per_day=row[11],
        diegetic_intensity=row[12],
        diegetic_frequency=row[13],
        updated_at=_to_dt(row[14]),
    )


def save_cadence_state(conn: sqlite3.Connection, state: CadenceState) -> None:
    now = state.updated_at or datetime.now(timezone.utc)
    values = _cadence_values(state, now)
    available = _cadence_table_columns(conn)
    columns = [column for column in _CADENCE_COLUMNS if column in available]
    if not columns:
        return
    update_columns = [column for column in columns if column != "subject_id"]
    conn.execute(
        f"""INSERT INTO checkin_cadence_state ({', '.join(columns)})
            VALUES ({', '.join('?' for _ in columns)})
            ON CONFLICT(subject_id) DO UPDATE SET
            {', '.join(f'{column} = excluded.{column}' for column in update_columns)}
            """,
        tuple(values[column] for column in columns),
    )


def persist_features(
    conn: sqlite3.Connection,
    subject_id: str,
    tick_id: str,
    features: CheckinFeatures,
    posture: str,
) -> int:
    payload = json.dumps(_features_to_dict(features), default=str)
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """INSERT INTO checkin_features (subject_id, tick_id, features_json, posture, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (subject_id, tick_id, payload, posture, now),
    )
    conn.commit()
    return int(cur.lastrowid)


def _features_to_dict(features: CheckinFeatures) -> dict:
    out: dict[str, Any] = {}
    for f in fields(features):
        value = getattr(features, f.name)
        if isinstance(value, datetime):
            out[f.name] = value.isoformat()
        else:
            out[f.name] = value
    return out


# ---------------------------------------------------------------------------
# Cadence reconciliation
# ---------------------------------------------------------------------------


_REACH_BASE = 0.7
_FOLLOWUP_DECAY_MIN_DAYS = 7
_FOLLOWUP_DECAY_REQUIRES_RECENT_MSG_DAYS = 7
_DIEGETIC_FREQUENCY_RELAX_WINDOW = timedelta(days=1)
_DIEGETIC_FREQUENCY_RELAX_STEP = 0.1
# RQ2: first diegetic reciprocity should start low and factual.
_DIEGETIC_BASELINE_INTENSITY = 0.2
# RQ2: first diegetic reciprocity should start at a moderate, not eager, cadence.
_DIEGETIC_BASELINE_FREQUENCY = 0.5
# RQ2: only positive reciprocity should raise the self-disclosure ceiling.
_DIEGETIC_POSITIVE_INTENSITY_STEP = 0.15
# RQ2: positive reciprocity can slightly increase cadence, but not abruptly.
_DIEGETIC_POSITIVE_FREQUENCY_STEP = 0.10
# RQ2: negative reaction should quickly reduce self-disclosure.
_DIEGETIC_NEGATIVE_INTENSITY_STEP = 0.20
# RQ2: negative reaction should sharply down-regulate future diegetic attempts.
_DIEGETIC_NEGATIVE_FREQUENCY_FACTOR = 0.6
# RQ2: silence becomes meaningful only after repeated ignored diegetic bids.
_DIEGETIC_DISENGAGEMENT_STREAK_THRESHOLD = 2
# RQ2: repeated silence should halve diegetic cadence to back off clearly.
_DIEGETIC_DISENGAGEMENT_FREQUENCY_FACTOR = 0.5
# RQ2: keep an explicit restraint ceiling below 1.0 even after positive reciprocity.
_DIEGETIC_MAX_INTENSITY = 0.9


def compute_reach_score(non_response_streak: int, followup_non_response_streak: int) -> float:
    """Spike §9 damping: 0.7 ^ (streak + 2*followup_streak)."""
    effective = max(0, int(non_response_streak)) + 2 * max(0, int(followup_non_response_streak))
    return _REACH_BASE ** effective


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _with_diegetic_baseline(state: CadenceState) -> CadenceState:
    intensity = state.diegetic_intensity
    frequency = state.diegetic_frequency
    if intensity is None:
        intensity = _DIEGETIC_BASELINE_INTENSITY
    if frequency is None:
        frequency = _DIEGETIC_BASELINE_FREQUENCY
    if intensity == state.diegetic_intensity and frequency == state.diegetic_frequency:
        return state
    return replace(
        state,
        diegetic_intensity=intensity,
        diegetic_frequency=frequency,
    )


def _normalized_reply_valence(raw: Any) -> float:
    try:
        if raw is None:
            return 0.0
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _apply_diegetic_answered_reaction(
    state: CadenceState,
    reply_valence: Any,
    now: datetime,
) -> CadenceState:
    state = _with_diegetic_baseline(state)
    intensity = state.diegetic_intensity
    frequency = state.diegetic_frequency
    if intensity is None or frequency is None:
        return state

    if _normalized_reply_valence(reply_valence) >= 0.0:
        intensity = _clamp(
            intensity + _DIEGETIC_POSITIVE_INTENSITY_STEP,
            0.0,
            _DIEGETIC_MAX_INTENSITY,
        )
        frequency = _clamp(
            frequency + _DIEGETIC_POSITIVE_FREQUENCY_STEP,
            0.0,
            1.0,
        )
    else:
        intensity = _clamp(
            intensity - _DIEGETIC_NEGATIVE_INTENSITY_STEP,
            0.0,
            _DIEGETIC_MAX_INTENSITY,
        )
        frequency = _clamp(
            frequency * _DIEGETIC_NEGATIVE_FREQUENCY_FACTOR,
            0.0,
            1.0,
        )

    return replace(
        state,
        diegetic_intensity=intensity,
        diegetic_frequency=frequency,
        # Reuse the cadence timestamp so the C2 relaxation hook does not
        # immediately counteract an explicit reaction-model update.
        last_decay_at=now,
    )


def _apply_diegetic_disengagement(state: CadenceState, now: datetime) -> CadenceState:
    state = _with_diegetic_baseline(state)
    frequency = state.diegetic_frequency
    if frequency is None:
        return state
    return replace(
        state,
        diegetic_frequency=_clamp(
            frequency * _DIEGETIC_DISENGAGEMENT_FREQUENCY_FACTOR,
            0.0,
            1.0,
        ),
        # Reuse the cadence timestamp so the C2 relaxation hook does not
        # immediately counteract an explicit reaction-model update.
        last_decay_at=now,
    )


def reconcile_cadence_outcome(state: CadenceState, event: Optional[dict]) -> CadenceState:
    event = normalize_decision_event_dict(event)
    now = _to_dt(event.get("now")) or datetime.now(timezone.utc)
    new = replace(state, updated_at=now)

    cap = event.get("boundary_frequency_cap_per_day")
    if cap is not None:
        try:
            new.frequency_cap_per_day = int(cap)
        except (TypeError, ValueError):
            pass
        new.last_boundary_at = now

    status = event.get("outcome_status")
    status_before = event.get("outcome_status_before")
    decision_type = event.get("decision_type")

    if status == "answered":
        new.non_response_streak = 0
        new.followup_non_response_streak = 0
        if decision_type == "diegetic":
            new.diegetic_non_response_streak = 0
        new.last_reply_at = now
        new.last_subject_msg_at = now
        if decision_type == "diegetic":
            new = _apply_diegetic_answered_reaction(new, event.get("reply_valence"), now)
    elif status == "unanswered_24h":
        # Only the explicit "delivered → unanswered_24h" transition penalises
        # cadence (spike §9.3). Replay paths from sparse historical rows must
        # not inflate the streak when outcome_status_before is missing.
        if status_before == "delivered":
            new.non_response_streak = state.non_response_streak + 1
            if decision_type == "followup":
                new.followup_non_response_streak = state.followup_non_response_streak + 1
            if decision_type == "diegetic":
                new.diegetic_non_response_streak = state.diegetic_non_response_streak + 1
                if (
                    new.diegetic_non_response_streak
                    >= _DIEGETIC_DISENGAGEMENT_STREAK_THRESHOLD
                ):
                    new = _apply_diegetic_disengagement(new, now)
        new.last_unanswered_delivery_at = now
    elif status == "delivered":
        new.last_delivered_initiative_at = now
        if decision_type == "diegetic":
            new.last_diegetic_delivered_at = now
    elif status in (None, "silent", "blocked"):
        # Silence / blocked do not penalise cadence.
        pass

    new = _maybe_apply_decay(new, now)
    new = _maybe_relax_diegetic_frequency(new, now)
    return new


def _maybe_apply_decay(state: CadenceState, now: datetime) -> CadenceState:
    """Spike §9: streak decays naturally if subject re-engages and time passes."""
    if state.non_response_streak <= 0:
        return state
    if state.last_subject_msg_at is None:
        return state
    if (now - state.last_subject_msg_at) > timedelta(days=_FOLLOWUP_DECAY_REQUIRES_RECENT_MSG_DAYS):
        return state
    if state.last_delivered_initiative_at is None:
        return state
    if (now - state.last_delivered_initiative_at) < timedelta(days=_FOLLOWUP_DECAY_MIN_DAYS):
        return state
    decayed = replace(
        state,
        non_response_streak=max(0, state.non_response_streak - 1),
        last_decay_at=now,
    )
    return decayed


def _maybe_relax_diegetic_frequency(state: CadenceState, now: datetime) -> CadenceState:
    """Nudge diegetic frequency back toward baseline on a small time window."""
    if state.diegetic_frequency is None:
        return state
    if state.diegetic_frequency >= 1.0:
        return state
    if state.last_decay_at is not None and (
        now - state.last_decay_at
    ) < _DIEGETIC_FREQUENCY_RELAX_WINDOW:
        return state
    return replace(
        state,
        diegetic_frequency=min(1.0, state.diegetic_frequency + _DIEGETIC_FREQUENCY_RELAX_STEP),
        last_decay_at=now,
    )


# ---------------------------------------------------------------------------
# Feature assembly
# ---------------------------------------------------------------------------


def build_checkin_features(
    *,
    subject_id: str,
    decision_type: str,
    relic_home: Path,
    hermes_home: Path,
    now: Optional[datetime] = None,
) -> CheckinFeatures:
    """Assemble a CheckinFeatures vector from on-disk state.

    All sources are optional: missing files fall through to safe defaults
    (silent / quiet downstream). Never reads raw message bodies.
    """
    now = now or datetime.now(timezone.utc)
    relic_home = Path(relic_home)
    hermes_home = Path(hermes_home)

    db_path = relic_home / "subjects" / subject_id / "relic.db"
    features = CheckinFeatures(subject_id=subject_id)

    state: Optional[CadenceState] = None
    posture_history: list[str] = []
    salience_top = 0.0
    topic_freshness = 1.0
    facet_status: Optional[str] = None
    asked_recently_12h = False
    last_reflect_age_days: Optional[int] = None

    daily_initiatives_today = 0
    if db_path.exists():
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            state = load_cadence_state(conn, subject_id)
            posture_history = _load_posture_history(conn, subject_id, limit=5)
            last_reflect_age_days = _load_last_reflect_age_days(conn, subject_id, now)
            facet_status, asked_recently_12h = _load_facet_state(conn, now)
        finally:
            conn.close()

    daily_initiatives_today += _count_today_initiatives(subject_id, relic_home, now)

    salience_top = _safe_load_salience_top(subject_id, relic_home)
    topic_freshness = _safe_load_topic_freshness(subject_id, relic_home)
    continuity_preference = _safe_load_continuity_preference(subject_id, relic_home)
    comfort_with_initiative = _safe_load_comfort_with_initiative(subject_id, relic_home)
    diegetic_tolerance = _safe_load_diegetic_tolerance(subject_id, relic_home)
    consent_active = _safe_load_consent(subject_id, relic_home)
    boundary_strict, risk_flag, freq_cap_from_boundary = _safe_load_boundary(subject_id, relic_home)
    quiet_hours_active = _safe_load_quiet_hours_active(subject_id, relic_home, now)
    time_since_last_msg, last_subject_msg_at, subject_avg_tokens_14d = _safe_load_subject_msg_state(
        hermes_home, now
    )

    if state is not None:
        features.non_response_streak = state.non_response_streak
        features.followup_non_response_streak = state.followup_non_response_streak
        features.last_delivered_initiative_at = state.last_delivered_initiative_at
        features.last_subject_msg_at = state.last_subject_msg_at or last_subject_msg_at
        if state.frequency_cap_per_day is not None:
            features.frequency_cap_per_day = state.frequency_cap_per_day
        features.diegetic_intensity = state.diegetic_intensity
        features.diegetic_frequency = state.diegetic_frequency
    else:
        features.last_subject_msg_at = last_subject_msg_at

    if freq_cap_from_boundary is not None and features.frequency_cap_per_day is None:
        features.frequency_cap_per_day = freq_cap_from_boundary

    features.consent_active = consent_active
    features.boundary_strict = boundary_strict
    features.risk_flag_active = risk_flag
    features.quiet_hours_active = quiet_hours_active
    features.daily_initiatives_today = daily_initiatives_today

    features.reach_score = compute_reach_score(
        features.non_response_streak,
        features.followup_non_response_streak,
    )
    features.salience_top = salience_top
    features.topic_freshness = topic_freshness
    features.continuity_preference = continuity_preference
    features.comfort_with_initiative = comfort_with_initiative
    features.diegetic_tolerance = diegetic_tolerance
    features.posture_history_last_5 = posture_history
    features.subject_avg_tokens_14d = subject_avg_tokens_14d
    features.time_since_last_subject_msg_sec = time_since_last_msg
    features.facet_status = facet_status
    features.asked_recently_12h = asked_recently_12h
    features.last_reflect_age_days = last_reflect_age_days

    return features


def backfill_from_decision_log(path: Path, conn: sqlite3.Connection) -> int:
    """Replay an append-only decision_events.jsonl to rebuild cadence state.

    Only DB state is rewritten — the JSONL is never mutated.
    """
    if not Path(path).exists():
        return 0
    replayed = 0
    states: dict[str, CadenceState] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            subject_id = row.get("subject_id")
            if not subject_id:
                continue
            state = states.get(subject_id) or load_cadence_state(conn, subject_id)
            event = normalize_decision_event_dict(row)
            states[subject_id] = reconcile_cadence_outcome(state, event)
            replayed += 1
    for state in states.values():
        save_cadence_state(conn, state)
    conn.commit()
    return replayed


# ---------------------------------------------------------------------------
# Best-effort source readers (Plan §Task 4, Step 5)
# ---------------------------------------------------------------------------


def _load_posture_history(conn: sqlite3.Connection, subject_id: str, *, limit: int) -> list[str]:
    try:
        rows = conn.execute(
            """SELECT posture FROM checkin_features
               WHERE subject_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (subject_id, limit),
        ).fetchall()
        return [r[0] for r in rows if r and r[0]]
    except sqlite3.DatabaseError:
        return []


def _load_last_reflect_age_days(
    conn: sqlite3.Connection,
    subject_id: str,
    now: datetime,
) -> Optional[int]:
    try:
        row = conn.execute(
            """SELECT created_at FROM checkin_features
               WHERE subject_id = ? AND posture = 'reflective_mirror'
               ORDER BY created_at DESC LIMIT 1""",
            (subject_id,),
        ).fetchone()
    except sqlite3.DatabaseError:
        return None
    if not row or not row[0]:
        return None
    dt = _to_dt(row[0])
    if dt is None:
        return None
    return max(0, int((now - dt).total_seconds() // 86400))


def _load_facet_state(
    conn: sqlite3.Connection,
    now: datetime,
) -> tuple[Optional[str], bool]:
    try:
        row = conn.execute(
            """SELECT facet_id, asked_at FROM checkin_exchanges
               WHERE facet_id IS NOT NULL
               ORDER BY asked_at DESC LIMIT 1""",
        ).fetchone()
    except sqlite3.DatabaseError:
        return None, False
    if not row:
        return None, False
    facet_id, asked_at_raw = row[0], row[1]
    asked_recently = False
    asked_at = _to_dt(asked_at_raw)
    if asked_at is not None and (now - asked_at) < timedelta(hours=12):
        asked_recently = True
    return facet_id, asked_recently


def _count_today_initiatives(subject_id: str, relic_home: Path, now: datetime) -> int:
    """Count DELIVER events for ``subject_id`` whose created_at is today (UTC).

    Reads the canonical RELIC_HOME-wide ``decision_events.jsonl`` so the
    frequency cap in select_decision actually fires. Returns 0 on missing
    file / parse errors.
    """
    log_path = Path(relic_home) / "decision_events.jsonl"
    if not log_path.exists():
        return 0
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("subject_id") != subject_id:
                    continue
                if row.get("decision") != "DELIVER":
                    continue
                created = _to_dt(row.get("created_at"))
                if created is None:
                    continue
                try:
                    if created.astimezone(timezone.utc) >= day_start:
                        count += 1
                except (TypeError, ValueError):
                    continue
    except OSError:
        return 0
    return count


def _safe_load_salience_top(subject_id: str, relic_home: Path) -> float:
    try:
        from relic.memory_dynamics import decay as _decay  # noqa: F401
    except Exception:
        return 0.0
    db_path = relic_home / "subjects" / subject_id / "relic.db"
    if not db_path.exists():
        return 0.0
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            row = conn.execute(
                "SELECT MAX(signal_strength) FROM observations",
            ).fetchone()
            return float(row[0] or 0.0) if row else 0.0
        finally:
            conn.close()
    except (sqlite3.DatabaseError, ValueError):
        return 0.0


def _safe_load_topic_freshness(subject_id: str, relic_home: Path) -> float:
    # AntiRepeatGate is consulted by the topic selector — the policy treats a
    # neutral 1.0 as "topic not yet known"; refinements land alongside Task 5.
    return 1.0


def _safe_load_project_calibration_float(
    subject_id: str,
    relic_home: Path,
    key: str,
    *,
    default: Optional[float] = 0.5,
) -> Optional[float]:
    response_path = relic_home / "subjects" / subject_id / "item_battery_response.json"
    baseline_path = relic_home / "subjects" / subject_id / "subject_baseline.json"

    for path, key_path in (
        (
            response_path,
            ("scores", "project_calibration", key),
        ),
        (
            baseline_path,
            ("item_battery", "scores", "project_calibration", key),
        ),
    ):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw = data
        for key in key_path:
            if not isinstance(raw, dict):
                raw = None
                break
            raw = raw.get(key)
        try:
            if raw is not None:
                return float(raw)
        except (TypeError, ValueError):
            continue

    return default


def _safe_load_continuity_preference(subject_id: str, relic_home: Path) -> float:
    return _safe_load_project_calibration_float(subject_id, relic_home, "continuity_preference")


def _safe_load_comfort_with_initiative(subject_id: str, relic_home: Path) -> float:
    return _safe_load_project_calibration_float(subject_id, relic_home, "comfort_with_initiative")


def _safe_load_diegetic_tolerance(subject_id: str, relic_home: Path) -> float:
    preferred = _safe_load_project_calibration_float(
        subject_id,
        relic_home,
        "fictional_diegesis_tolerance",
        default=None,
    )
    if preferred is not None:
        return preferred

    fallback_values: list[float] = []
    for key in (
        "embodiment_world_tolerance",
        "routine_fragment_tolerance",
        "first_person_life_fragment_tolerance",
        "world_evolution_tolerance",
    ):
        value = _safe_load_project_calibration_float(
            subject_id,
            relic_home,
            key,
            default=None,
        )
        if value is not None:
            fallback_values.append(value)

    if fallback_values:
        return sum(fallback_values) / len(fallback_values)

    return 0.45


def _safe_load_consent(subject_id: str, relic_home: Path) -> bool:
    consent_path = relic_home / "subjects" / subject_id / "consent_record.json"
    if not consent_path.exists():
        return True
    try:
        data = json.loads(consent_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    # Active consent unless explicitly revoked / paused.
    if data.get("revoked"):
        return False
    if data.get("paused"):
        return False
    return True


def _safe_load_boundary(
    subject_id: str,
    relic_home: Path,
) -> tuple[bool, bool, Optional[int]]:
    boundary_path = relic_home / "subjects" / subject_id / "boundary_policy.json"
    strict = False
    risk_flag = False
    cap = None
    if not boundary_path.exists():
        return strict, risk_flag, cap
    try:
        data = json.loads(boundary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return strict, risk_flag, cap
    if data.get("careful_distancing_enabled"):
        strict = True
    if data.get("risk_flags"):
        risk_flag = True
    cap_value = data.get("maximum_daily_initiatives")
    if isinstance(cap_value, (int, float)):
        cap = int(cap_value)
    return strict, risk_flag, cap


def _safe_load_quiet_hours_active(subject_id: str, relic_home: Path, now: datetime) -> bool:
    # Quiet hours enforcement is owned by the safety gate (_is_quiet_hours);
    # the feature vector is used only as a hint downstream.
    return False


def _safe_load_subject_msg_state(
    hermes_home: Path,
    now: datetime,
) -> tuple[Optional[int], Optional[datetime], Optional[float]]:
    """Read last-subject-msg state from Hermes ``state.db``.

    Real Hermes schema uses ``timestamp REAL`` (epoch seconds). Test fixtures
    in this repo use the legacy ``created_at TEXT`` column, so we detect which
    column exists at runtime and adapt — otherwise the production reads
    silently fall back to None for every tick.
    """
    state_db = Path(hermes_home) / "state.db"
    if not state_db.exists():
        return None, None, None
    try:
        conn = sqlite3.connect(str(state_db), timeout=5.0)
    except sqlite3.DatabaseError:
        return None, None, None
    try:
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()}
        except sqlite3.DatabaseError:
            return None, None, None

        last_dt: Optional[datetime] = None
        time_since: Optional[int] = None
        avg_tokens: Optional[float] = None

        if "timestamp" in cols:
            try:
                row = conn.execute(
                    "SELECT MAX(timestamp) FROM messages WHERE role = 'user'",
                ).fetchone()
            except sqlite3.DatabaseError:
                row = None
            if row and row[0] is not None:
                try:
                    last_dt = datetime.fromtimestamp(float(row[0]), tz=timezone.utc)
                except (TypeError, ValueError, OSError):
                    last_dt = None
            try:
                cutoff = (now - timedelta(days=14)).timestamp()
                avg_row = conn.execute(
                    "SELECT AVG(LENGTH(content) / 4.0) FROM messages "
                    "WHERE role = 'user' AND timestamp >= ?",
                    (cutoff,),
                ).fetchone()
                avg_tokens = (
                    float(avg_row[0]) if avg_row and avg_row[0] is not None else None
                )
            except (sqlite3.DatabaseError, ValueError, TypeError):
                avg_tokens = None
        elif "created_at" in cols:
            try:
                row = conn.execute(
                    "SELECT MAX(created_at) FROM messages WHERE role = 'user'",
                ).fetchone()
            except sqlite3.DatabaseError:
                row = None
            if row and row[0]:
                last_dt = _to_dt(row[0])
            try:
                avg_row = conn.execute(
                    "SELECT AVG(LENGTH(content) / 4.0) FROM messages "
                    "WHERE role = 'user' AND created_at >= ?",
                    ((now - timedelta(days=14)).isoformat(),),
                ).fetchone()
                avg_tokens = (
                    float(avg_row[0]) if avg_row and avg_row[0] is not None else None
                )
            except (sqlite3.DatabaseError, ValueError, TypeError):
                avg_tokens = None
        else:
            return None, None, None

        if last_dt is not None:
            try:
                time_since = max(0, int((now - last_dt).total_seconds()))
            except (TypeError, ValueError):
                time_since = None
        return time_since, last_dt, avg_tokens
    finally:
        try:
            conn.close()
        except Exception:
            pass
