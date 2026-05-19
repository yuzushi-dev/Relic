"""Tests for followup postures + last_exchange context section (Plan §Task 8)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from relic.checkin.context_builder import (
    build_deliver_context,
    build_last_exchange_section,
)
from relic.checkin.db_init import init_db
from relic.checkin.policy import (
    CheckinFeatures,
    EventType,
    Posture,
    select_decision,
)


def test_followup_warm_when_no_streak():
    f = CheckinFeatures(reach_score=1.0, time_since_last_subject_msg_sec=3600)
    d = select_decision(f, decision_type="followup", policy_enabled=True)
    assert d.event_type is EventType.FOLLOWUP
    assert d.posture is Posture.FOLLOW_UP_WARM


def test_followup_terse_when_streak_positive():
    f = CheckinFeatures(
        reach_score=0.7,
        non_response_streak=1,
        time_since_last_subject_msg_sec=3600,
    )
    d = select_decision(f, decision_type="followup", policy_enabled=True)
    assert d.event_type is EventType.FOLLOWUP
    assert d.posture is Posture.FOLLOW_UP_TERSE


def _seed_subject(tmp_path: Path, subject_id: str) -> Path:
    subject_dir = tmp_path / "relic" / "subjects" / subject_id
    subject_dir.mkdir(parents=True)
    (subject_dir / "delivery_policy.json").write_text(
        json.dumps({"consent_for_active_elicitation": True}),
        encoding="utf-8",
    )
    db_path = subject_dir / "relic.db"
    conn = init_db(db_path)
    conn.close()
    return db_path


def test_build_last_exchange_section_returns_bounded_summary(tmp_path: Path):
    db_path = _seed_subject(tmp_path, "s1")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO checkin_exchanges
               (facet_id, question_text, reply_text, asked_at, reply_captured_at,
                response_latency_seconds, posture)
               VALUES (?, ?, ?, datetime('now', '-2 hours'), datetime('now'),
                       7200, 'follow_up_warm')""",
            ("cognitive.decision_speed", "domanda", "risposta sintetica"),
        )
        conn.commit()
    finally:
        conn.close()

    section = build_last_exchange_section(db_path)
    assert "ultimo scambio" in section
    assert "domanda" in section
    assert "risposta sintetica" in section
    assert "latenza_sec: 7200" in section
    assert "postura: follow_up_warm" in section


def test_followup_terse_context_skips_observations(tmp_path: Path):
    relic_home = tmp_path / "relic"
    db_path = _seed_subject(tmp_path, "s1")
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO observations (facet_id, source_type, content, created_at)
               VALUES (?, 'checkin_reply', 'osservazione che non deve apparire', datetime('now'))""",
            ("cognitive.decision_speed",),
        )
        conn.execute(
            """INSERT INTO checkin_exchanges
               (facet_id, question_text, reply_text, asked_at, reply_captured_at)
               VALUES (?, ?, ?, datetime('now', '-1 hours'), datetime('now'))""",
            ("cognitive.decision_speed", "ce l'hai fatta?", "sì"),
        )
        conn.commit()
    finally:
        conn.close()

    result = build_deliver_context(
        "s1",
        hermes_home=hermes_home,
        relic_home=relic_home,
        event_type="followup",
        posture="follow_up_terse",
    )
    assert "ce l'hai fatta?" in result
    assert "osservazione che non deve apparire" not in result


def test_followup_warm_context_includes_subject_messages(tmp_path: Path):
    relic_home = tmp_path / "relic"
    db_path = _seed_subject(tmp_path, "s1")
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT INTO checkin_exchanges
               (facet_id, question_text, reply_text, asked_at, reply_captured_at)
               VALUES (?, ?, ?, datetime('now', '-1 hours'), datetime('now'))""",
            ("cognitive.decision_speed", "ciao", "sì"),
        )
        conn.commit()
    finally:
        conn.close()

    result = build_deliver_context(
        "s1",
        hermes_home=hermes_home,
        relic_home=relic_home,
        event_type="followup",
        posture="follow_up_warm",
    )
    assert "ultimo scambio" in result
