"""Tests for relic.checkin.features.build_checkin_features (Plan §Task 4)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relic.checkin.db_init import init_db
from relic.checkin.features import (
    CadenceState,
    build_checkin_features,
    load_cadence_state,
    persist_features,
    save_cadence_state,
)
from relic.checkin.policy import CheckinFeatures


def _make_db(tmp_path: Path, subject_id: str) -> Path:
    db_path = tmp_path / "relic" / "subjects" / subject_id / "relic.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(db_path)
    conn.close()
    return db_path


def test_build_features_returns_defaults_without_state(tmp_path: Path):
    features = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=tmp_path / "relic",
        hermes_home=tmp_path / "hermes",
    )
    assert features.non_response_streak == 0
    assert features.followup_non_response_streak == 0
    assert features.reach_score == 1.0
    assert features.consent_active is True


def test_build_features_loads_cadence_streak(tmp_path: Path):
    relic_home = tmp_path / "relic"
    hermes_home = tmp_path / "hermes"
    db_path = _make_db(tmp_path, "s1")
    conn = sqlite3.connect(str(db_path))
    try:
        state = CadenceState(
            subject_id="s1",
            non_response_streak=2,
            followup_non_response_streak=1,
            updated_at=datetime.now(timezone.utc),
        )
        save_cadence_state(conn, state)
        conn.commit()
    finally:
        conn.close()
    features = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert features.non_response_streak == 2
    assert features.followup_non_response_streak == 1
    assert features.reach_score == pytest.approx(0.7 ** 4)


def test_cadence_state_round_trips_diegetic_columns(tmp_path: Path):
    db_path = _make_db(tmp_path, "s1")
    now = datetime.now(timezone.utc)

    conn = sqlite3.connect(str(db_path))
    try:
        save_cadence_state(
            conn,
            CadenceState(
                subject_id="s1",
                diegetic_non_response_streak=2,
                last_diegetic_delivered_at=now - timedelta(hours=3),
                diegetic_intensity=0.7,
                diegetic_frequency=0.4,
                updated_at=now,
            ),
        )
        conn.commit()

        state = load_cadence_state(conn, "s1")
    finally:
        conn.close()

    assert state.diegetic_non_response_streak == 2
    assert state.last_diegetic_delivered_at == now - timedelta(hours=3)
    assert state.diegetic_intensity == pytest.approx(0.7)
    assert state.diegetic_frequency == pytest.approx(0.4)


def test_build_features_loads_diegetic_runtime_knobs_from_cadence_state(tmp_path: Path):
    relic_home = tmp_path / "relic"
    hermes_home = tmp_path / "hermes"
    db_path = _make_db(tmp_path, "s1")
    conn = sqlite3.connect(str(db_path))
    try:
        save_cadence_state(
            conn,
            CadenceState(
                subject_id="s1",
                diegetic_intensity=0.2,
                diegetic_frequency=0.8,
                updated_at=datetime.now(timezone.utc),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    features = build_checkin_features(
        subject_id="s1",
        decision_type="diegetic",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )

    assert features.diegetic_intensity == pytest.approx(0.2)
    assert features.diegetic_frequency == pytest.approx(0.8)


def test_build_features_reports_boundary_risk_flag(tmp_path: Path):
    relic_home = tmp_path / "relic"
    subject_dir = relic_home / "subjects" / "s1"
    subject_dir.mkdir(parents=True)
    (subject_dir / "boundary_policy.json").write_text(
        json.dumps(
            {
                "careful_distancing_enabled": True,
                "risk_flags": ["crisis_language"],
                "maximum_daily_initiatives": 2,
            }
        ),
        encoding="utf-8",
    )
    features = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=relic_home,
        hermes_home=tmp_path / "hermes",
    )
    assert features.risk_flag_active is True
    assert features.boundary_strict is True
    assert features.frequency_cap_per_day == 2


@pytest.mark.parametrize(
    ("boundary_policy", "expected"),
    [
        ({}, False),
        ({"diegetic_enabled": False}, False),
        ({"diegetic_enabled": True}, True),
    ],
)
def test_build_features_loads_diegetic_enabled_from_boundary_policy(
    tmp_path: Path,
    boundary_policy: dict,
    expected: bool,
):
    relic_home = tmp_path / "relic"
    subject_dir = relic_home / "subjects" / "s1"
    subject_dir.mkdir(parents=True)
    (subject_dir / "boundary_policy.json").write_text(
        json.dumps(boundary_policy),
        encoding="utf-8",
    )

    features = build_checkin_features(
        subject_id="s1",
        decision_type="diegetic",
        relic_home=relic_home,
        hermes_home=tmp_path / "hermes",
    )

    assert features.diegetic_enabled is expected


def test_persist_features_returns_features_id_and_posture_history(tmp_path: Path):
    db_path = _make_db(tmp_path, "s1")
    conn = sqlite3.connect(str(db_path))
    try:
        fid1 = persist_features(conn, "s1", "tick-1", CheckinFeatures(subject_id="s1"), posture="observe")
        fid2 = persist_features(conn, "s1", "tick-2", CheckinFeatures(subject_id="s1"), posture="brief_share")
        assert fid2 > fid1
    finally:
        conn.close()

    features = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=tmp_path / "relic",
        hermes_home=tmp_path / "hermes",
    )
    assert features.posture_history_last_5[0] == "brief_share"
    assert "observe" in features.posture_history_last_5


def test_subject_msg_state_handles_real_hermes_schema(tmp_path):
    """Production Hermes state.db uses ``timestamp REAL``, not ``created_at TEXT``.
    build_checkin_features must adapt to both."""
    import sqlite3
    from datetime import datetime, timezone

    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    db = hermes_home / "state.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)"
        )
        now_ts = datetime.now(timezone.utc).timestamp()
        conn.execute(
            "INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
            ("user", "ciao tutto bene", now_ts - 60),
        )
        conn.commit()
    finally:
        conn.close()

    f = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=tmp_path / "relic",
        hermes_home=hermes_home,
    )
    assert f.time_since_last_subject_msg_sec is not None
    assert 0 <= f.time_since_last_subject_msg_sec <= 120
    assert f.subject_avg_tokens_14d is not None


def test_daily_initiatives_today_populated_from_decision_log(tmp_path):
    import json
    from datetime import datetime, timezone

    relic_home = tmp_path / "relic"
    relic_home.mkdir()
    log = relic_home / "decision_events.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        {"subject_id": "s1", "decision": "DELIVER", "created_at": now},
        {"subject_id": "s1", "decision": "DELIVER", "created_at": now},
        {"subject_id": "s2", "decision": "DELIVER", "created_at": now},
        {"subject_id": "s1", "decision": "NO_REPLY", "created_at": now},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    f = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=relic_home,
        hermes_home=tmp_path / "hermes",
    )
    assert f.daily_initiatives_today == 2


def test_load_cadence_state_defaults_missing_diegetic_columns_on_legacy_schema(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """CREATE TABLE checkin_cadence_state (
                subject_id TEXT PRIMARY KEY,
                non_response_streak INTEGER NOT NULL DEFAULT 0,
                followup_non_response_streak INTEGER NOT NULL DEFAULT 0,
                last_delivered_initiative_at TEXT,
                last_unanswered_delivery_at TEXT,
                last_reply_at TEXT,
                last_subject_msg_at TEXT,
                last_boundary_at TEXT,
                last_decay_at TEXT,
                frequency_cap_per_day INTEGER,
                updated_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """INSERT INTO checkin_cadence_state (
                subject_id, non_response_streak, followup_non_response_streak, updated_at
            ) VALUES (?, ?, ?, ?)""",
            ("s1", 4, 1, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()

        state = load_cadence_state(conn, "s1")
    finally:
        conn.close()

    assert state.non_response_streak == 4
    assert state.followup_non_response_streak == 1
    assert state.diegetic_non_response_streak == 0
    assert state.last_diegetic_delivered_at is None
    assert state.diegetic_intensity is None
    assert state.diegetic_frequency is None
