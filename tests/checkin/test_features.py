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
