"""Tests for relic.checkin.outcome_reconciler (Plan §Task 4b)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relic.checkin.db_init import init_db
from relic.checkin.features import load_cadence_state
from relic.checkin.outcome_reconciler import reconcile_due_outcomes


def _seed_subject_db(tmp_path: Path, subject_id: str) -> Path:
    db_path = tmp_path / "subjects" / subject_id / "relic.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(db_path)
    conn.close()
    return db_path


def _append_event(relic_home: Path, event: dict) -> None:
    path = relic_home / "decision_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def _seed_hermes_state(hermes_home: Path) -> Path:
    state_db = hermes_home / "state.db"
    state_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(state_db))
    try:
        conn.execute(
            """CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        conn.commit()
    finally:
        conn.close()
    return state_db


def _delivered_event(subject_id: str, *, delivered_at: datetime, dtype: str = "checkin") -> dict:
    return {
        "decision": "DELIVER",
        "subject_id": subject_id,
        "gumi_instance_id": "g1",
        "hermes_profile_id": "p1",
        "decision_type": dtype,
        "event_kind": dtype,
        "outcome_status": "delivered",
        "created_at": delivered_at.isoformat(),
        "delivered_at": delivered_at.isoformat(),
        "response_deadline_at": (delivered_at + timedelta(hours=24)).isoformat(),
        "event_id": f"evt-{delivered_at.timestamp():.0f}",
    }


def test_delivered_with_no_reply_becomes_unanswered_24h(tmp_path: Path):
    relic_home = tmp_path
    hermes_home = tmp_path / "hermes"
    _seed_subject_db(relic_home, "s1")
    _seed_hermes_state(hermes_home)

    delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
    _append_event(relic_home, _delivered_event("s1", delivered_at=delivered_at))

    emitted = reconcile_due_outcomes(
        "s1",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert emitted == 1

    events = [
        json.loads(l) for l in (relic_home / "decision_events.jsonl").read_text().splitlines() if l.strip()
    ]
    transitions = [e for e in events if e.get("outcome_status") == "unanswered_24h"]
    assert len(transitions) == 1
    assert transitions[0]["outcome_status_before"] == "delivered"


def test_reply_before_deadline_skips_transition(tmp_path: Path):
    relic_home = tmp_path
    hermes_home = tmp_path / "hermes"
    _seed_subject_db(relic_home, "s1")
    state_db = _seed_hermes_state(hermes_home)

    delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
    _append_event(relic_home, _delivered_event("s1", delivered_at=delivered_at))

    conn = sqlite3.connect(str(state_db))
    try:
        conn.execute(
            "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
            ("user", "thanks", (delivered_at + timedelta(hours=2)).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    emitted = reconcile_due_outcomes(
        "s1",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert emitted == 0


def test_idempotent_when_run_twice(tmp_path: Path):
    relic_home = tmp_path
    hermes_home = tmp_path / "hermes"
    _seed_subject_db(relic_home, "s1")
    _seed_hermes_state(hermes_home)

    delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
    _append_event(relic_home, _delivered_event("s1", delivered_at=delivered_at))

    first = reconcile_due_outcomes("s1", relic_home=relic_home, hermes_home=hermes_home)
    second = reconcile_due_outcomes("s1", relic_home=relic_home, hermes_home=hermes_home)
    assert first == 1
    assert second == 0


def test_increments_cadence_streak_after_transition(tmp_path: Path):
    relic_home = tmp_path
    hermes_home = tmp_path / "hermes"
    db_path = _seed_subject_db(relic_home, "s1")
    _seed_hermes_state(hermes_home)

    delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
    _append_event(relic_home, _delivered_event("s1", delivered_at=delivered_at))

    reconcile_due_outcomes("s1", relic_home=relic_home, hermes_home=hermes_home)

    conn = sqlite3.connect(str(db_path))
    try:
        state = load_cadence_state(conn, "s1")
    finally:
        conn.close()
    assert state.non_response_streak == 1


def test_non_ask_delivery_with_reply_does_not_transition(tmp_path: Path):
    relic_home = tmp_path
    hermes_home = tmp_path / "hermes"
    db_path = _seed_subject_db(relic_home, "s1")
    state_db = _seed_hermes_state(hermes_home)

    delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
    event = _delivered_event("s1", delivered_at=delivered_at, dtype="checkin")
    event["event_kind"] = "observe"
    _append_event(relic_home, event)

    conn = sqlite3.connect(str(state_db))
    try:
        conn.execute(
            "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
            ("user", "ciao", (delivered_at + timedelta(hours=23)).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    emitted = reconcile_due_outcomes("s1", relic_home=relic_home, hermes_home=hermes_home)
    assert emitted == 0

    conn = sqlite3.connect(str(db_path))
    try:
        state = load_cadence_state(conn, "s1")
    finally:
        conn.close()
    assert state.non_response_streak == 0


def test_real_hermes_schema_with_reply_skips_transition(tmp_path):
    """Production Hermes state.db uses ``timestamp REAL``; the reconciler
    must read the right column or every reply is invisible to it."""
    import sqlite3
    from datetime import datetime, timedelta, timezone

    relic_home = tmp_path
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _seed_subject_db(relic_home, "s1")

    state_db = hermes_home / "state.db"
    conn = sqlite3.connect(str(state_db))
    try:
        conn.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)"
        )
        delivered_at = datetime.now(timezone.utc) - timedelta(hours=25)
        conn.execute(
            "INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
            ("user", "ciao", (delivered_at + timedelta(hours=2)).timestamp()),
        )
        conn.commit()
    finally:
        conn.close()

    _append_event(relic_home, _delivered_event("s1", delivered_at=delivered_at))
    emitted = reconcile_due_outcomes("s1", relic_home=relic_home, hermes_home=hermes_home)
    assert emitted == 0
