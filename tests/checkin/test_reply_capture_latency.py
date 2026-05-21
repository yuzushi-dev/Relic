"""Tests for reply_capture latency + cadence reset (Plan §Task 4, Step 6)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relic.checkin.db_init import init_db
from relic.checkin.features import CadenceState, load_cadence_state, save_cadence_state
from relic.checkin.reply_capture import capture_reply_if_pending


def _seed_subject(tmp_path: Path, subject_id: str) -> Path:
    subject_dir = tmp_path / "subjects" / subject_id
    subject_dir.mkdir(parents=True)
    (subject_dir / "delivery_policy.json").write_text(
        json.dumps({"consent_for_active_elicitation": True}),
        encoding="utf-8",
    )
    db_path = subject_dir / "relic.db"
    conn = init_db(db_path)
    conn.close()
    return db_path


def _insert_pending_exchange(db_path: Path, asked_at: datetime) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            """INSERT INTO checkin_exchanges (facet_id, question_text, asked_at)
               VALUES (?, ?, ?)""",
            ("cognitive.decision_speed", "test?", asked_at.isoformat()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _append_decision_event(relic_home: Path, event: dict) -> None:
    path = relic_home / "decision_events.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8") + json.dumps(event) + "\n" if path.exists() else json.dumps(event) + "\n",
        encoding="utf-8",
    )


def test_capture_reply_sets_response_latency_seconds(tmp_path: Path):
    relic_home = tmp_path
    db_path = _seed_subject(relic_home, "s1")
    asked_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    exchange_id = _insert_pending_exchange(db_path, asked_at)

    captured = capture_reply_if_pending(
        "thanks for asking",
        subject_id="s1",
        relic_home=str(relic_home),
    )
    assert captured is True

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT response_latency_seconds FROM checkin_exchanges WHERE id = ?",
            (exchange_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] is not None
    assert 1700 <= row[0] <= 2000  # ~1800s with tolerance


def test_capture_reply_leaves_latency_null_for_malformed_asked_at(tmp_path: Path):
    relic_home = tmp_path
    db_path = _seed_subject(relic_home, "s1")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO checkin_exchanges (facet_id, question_text, asked_at)
               VALUES (?, ?, ?)""",
            ("cognitive.decision_speed", "test?", "not-a-timestamp"),
        )
        conn.commit()
    finally:
        conn.close()

    capture_reply_if_pending(
        "thanks for asking",
        subject_id="s1",
        relic_home=str(relic_home),
    )

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT response_latency_seconds FROM checkin_exchanges",
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] is None


def test_reply_capture_resets_existing_cadence_streaks_without_diegetic_match(tmp_path: Path):
    relic_home = tmp_path
    db_path = _seed_subject(relic_home, "s1")
    _insert_pending_exchange(db_path, datetime.now(timezone.utc) - timedelta(minutes=5))

    conn = sqlite3.connect(str(db_path))
    try:
        save_cadence_state(
            conn,
            CadenceState(
                subject_id="s1",
                non_response_streak=3,
                followup_non_response_streak=2,
                diegetic_non_response_streak=4,
                updated_at=datetime.now(timezone.utc),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    capture_reply_if_pending(
        "ehi tutto bene",
        subject_id="s1",
        relic_home=str(relic_home),
    )

    conn = sqlite3.connect(str(db_path))
    try:
        state = load_cadence_state(conn, "s1")
    finally:
        conn.close()
    assert state.non_response_streak == 0
    assert state.followup_non_response_streak == 0
    assert state.diegetic_non_response_streak == 4
    assert state.last_reply_at is not None


def test_reply_capture_resets_diegetic_streak_when_latest_delivery_is_diegetic(tmp_path: Path):
    relic_home = tmp_path
    db_path = _seed_subject(relic_home, "s1")
    delivered_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    _insert_pending_exchange(db_path, delivered_at)
    _append_decision_event(
        relic_home,
        {
            "decision": "DELIVER",
            "subject_id": "s1",
            "decision_type": "diegetic",
            "outcome_status": "delivered",
            "created_at": delivered_at.isoformat(),
            "delivered_at": delivered_at.isoformat(),
            "response_deadline_at": (delivered_at + timedelta(hours=24)).isoformat(),
            "event_id": "evt-diegetic",
        },
    )

    conn = sqlite3.connect(str(db_path))
    try:
        save_cadence_state(
            conn,
            CadenceState(
                subject_id="s1",
                non_response_streak=3,
                followup_non_response_streak=2,
                diegetic_non_response_streak=4,
                updated_at=datetime.now(timezone.utc),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    capture_reply_if_pending(
        "ehi tutto bene",
        subject_id="s1",
        relic_home=str(relic_home),
    )

    conn = sqlite3.connect(str(db_path))
    try:
        state = load_cadence_state(conn, "s1")
    finally:
        conn.close()
    assert state.non_response_streak == 0
    assert state.followup_non_response_streak == 0
    assert state.diegetic_non_response_streak == 0
    assert state.last_reply_at is not None
