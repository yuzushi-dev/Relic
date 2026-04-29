"""Unit tests for relic_health_monitor."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from mnemon.relic_health_monitor import (
    COVERAGE_CRIT,
    COVERAGE_WARN,
    AVG_CONF_WARN,
    AVG_CONF_CRIT,
    LOOP_RISK_WARN,
    LOOP_RISK_CRIT,
    NEGLECTED_CONF,
    compute_metrics,
    find_neglected_facets,
    format_report,
    score_severity,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE facets (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL DEFAULT 'cognitive'
        );
        CREATE TABLE traits (
            facet_id TEXT PRIMARY KEY,
            confidence REAL DEFAULT 0.0,
            observation_count INTEGER DEFAULT 0,
            last_synthesis_at TEXT
        );
        CREATE TABLE observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facet_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            signal_strength REAL DEFAULT 0.5,
            signal_position REAL,
            created_at TEXT NOT NULL
        );
    """)
    return db


def _add_facet(db, facet_id: str, confidence: float, obs_count: int = 5,
               category: str = "cognitive") -> None:
    db.execute("INSERT OR REPLACE INTO facets (id, category) VALUES (?, ?)",
               (facet_id, category))
    db.execute(
        "INSERT OR REPLACE INTO traits (facet_id, confidence, observation_count) VALUES (?,?,?)",
        (facet_id, confidence, obs_count),
    )
    db.commit()


def _add_obs(db, facet_id: str, source_type: str, days_ago: float = 1.0) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    db.execute(
        "INSERT INTO observations (facet_id, source_type, created_at) VALUES (?,?,?)",
        (facet_id, source_type, ts),
    )
    db.commit()


# ── compute_metrics ───────────────────────────────────────────────────────────

def test_compute_metrics_empty_returns_error():
    db = _make_db()
    result = compute_metrics(db)
    assert "error" in result


def test_compute_metrics_avg_confidence():
    db = _make_db()
    _add_facet(db, "f1", 0.8)
    _add_facet(db, "f2", 0.4)
    _add_facet(db, "f3", 0.2)
    m = compute_metrics(db)
    assert m["avg_confidence"] == pytest.approx((0.8 + 0.4 + 0.2) / 3, abs=1e-4)


def test_compute_metrics_coverage_pct():
    db = _make_db()
    _add_facet(db, "f1", 0.8)   # covered
    _add_facet(db, "f2", 0.4)   # covered
    _add_facet(db, "f3", 0.1)   # not covered
    m = compute_metrics(db)
    assert m["facets_covered"] == 2
    assert m["facets_total"] == 3
    assert m["coverage_pct"] == pytest.approx(2 / 3, abs=1e-4)


def test_compute_metrics_bootstrap_loop_risk_zero():
    db = _make_db()
    _add_facet(db, "f1", 0.6)
    _add_obs(db, "f1", "passive_chat", days_ago=1)
    _add_obs(db, "f1", "passive_chat", days_ago=2)
    m = compute_metrics(db)
    assert m["bootstrap_loop_risk"] == 0.0
    assert m["obs_7d_independent"] == 2


def test_compute_metrics_bootstrap_loop_risk_high():
    db = _make_db()
    _add_facet(db, "f1", 0.6)
    for _ in range(8):
        _add_obs(db, "f1", "session_behavioral", days_ago=1)
    _add_obs(db, "f1", "passive_chat", days_ago=2)
    m = compute_metrics(db)
    # 8 ai-mediated, 1 independent → 8/9
    assert m["bootstrap_loop_risk"] == pytest.approx(8 / 9, abs=1e-4)
    assert m["obs_7d_ai_mediated"] == 8
    assert m["obs_7d_independent"] == 1


def test_compute_metrics_old_obs_excluded_from_7d():
    db = _make_db()
    _add_facet(db, "f1", 0.6)
    _add_obs(db, "f1", "session_behavioral", days_ago=10)  # outside 7d window
    m = compute_metrics(db)
    assert m["bootstrap_loop_risk"] == 0.0
    assert m["obs_7d_total"] == 0


# ── score_severity ────────────────────────────────────────────────────────────

def test_score_severity_healthy():
    metrics = {"coverage_pct": 0.75, "avg_confidence": 0.5, "bootstrap_loop_risk": 0.3}
    assert score_severity(metrics) == "healthy"


def test_score_severity_degraded_coverage():
    metrics = {"coverage_pct": COVERAGE_WARN - 0.01, "avg_confidence": 0.5,
               "bootstrap_loop_risk": 0.3}
    assert score_severity(metrics) == "degraded"


def test_score_severity_degraded_confidence():
    metrics = {"coverage_pct": 0.75, "avg_confidence": AVG_CONF_WARN - 0.01,
               "bootstrap_loop_risk": 0.3}
    assert score_severity(metrics) == "degraded"


def test_score_severity_degraded_loop():
    metrics = {"coverage_pct": 0.75, "avg_confidence": 0.5,
               "bootstrap_loop_risk": LOOP_RISK_WARN + 0.01}
    assert score_severity(metrics) == "degraded"


def test_score_severity_critical_loop():
    metrics = {"coverage_pct": 0.75, "avg_confidence": 0.5,
               "bootstrap_loop_risk": LOOP_RISK_CRIT + 0.01}
    assert score_severity(metrics) == "critical"


def test_score_severity_critical_coverage():
    metrics = {"coverage_pct": COVERAGE_CRIT - 0.01, "avg_confidence": 0.5,
               "bootstrap_loop_risk": 0.3}
    assert score_severity(metrics) == "critical"


# ── find_neglected_facets ─────────────────────────────────────────────────────

def test_find_neglected_facets_returns_low_confidence():
    db = _make_db()
    _add_facet(db, "bad_facet", 0.10)
    _add_facet(db, "good_facet", 0.80)
    neglected = find_neglected_facets(db)
    ids = [n["facet_id"] for n in neglected]
    assert "bad_facet" in ids
    assert "good_facet" not in ids


def test_find_neglected_facets_counts_recent_independent():
    db = _make_db()
    _add_facet(db, "f1", 0.15)
    _add_obs(db, "f1", "passive_chat", days_ago=3)     # independent, recent
    _add_obs(db, "f1", "session_behavioral", days_ago=1)  # loop obs, ignored
    neglected = find_neglected_facets(db)
    f1 = next(n for n in neglected if n["facet_id"] == "f1")
    assert f1["recent_independent_obs"] == 1


def test_find_neglected_capped_at_20():
    db = _make_db()
    for i in range(25):
        _add_facet(db, f"f{i}", 0.05)
    neglected = find_neglected_facets(db)
    assert len(neglected) <= 20


# ── format_report ─────────────────────────────────────────────────────────────

def test_format_report_contains_metrics():
    metrics = {
        "avg_confidence": 0.312,
        "coverage_pct": 0.54,
        "facets_covered": 32,
        "facets_total": 60,
        "bootstrap_loop_risk": 0.759,
        "obs_7d_total": 100,
        "obs_7d_ai_mediated": 76,
        "obs_7d_independent": 24,
    }
    report = format_report(metrics, [], "critical")
    assert "CRITICAL" in report
    assert "0.3120" in report
    assert "75.9%" in report
    assert "54.0%" in report


def test_format_report_shows_neglected_facets():
    metrics = {
        "avg_confidence": 0.2, "coverage_pct": 0.4, "facets_covered": 24,
        "facets_total": 60, "bootstrap_loop_risk": 0.5,
        "obs_7d_total": 10, "obs_7d_ai_mediated": 5, "obs_7d_independent": 5,
    }
    neglected = [{"facet_id": "emotional.stress_response", "category": "emotional",
                  "confidence": 0.05, "observation_count": 2, "recent_independent_obs": 0}]
    report = format_report(metrics, neglected, "degraded")
    assert "emotional.stress_response" in report
    assert "Neglected Facets" in report


# ── apply_remediation ─────────────────────────────────────────────────────────

import tempfile, json as _json
from pathlib import Path as _Path
from mnemon.relic_health_monitor import apply_remediation, HEALTH_OVERRIDES_FILE, RELIC_DIR


def test_apply_remediation_writes_file_when_critical(tmp_path, monkeypatch):
    monkeypatch.setattr("mnemon.relic_health_monitor.RELIC_DIR", tmp_path)
    monkeypatch.setattr("mnemon.relic_health_monitor.HEALTH_OVERRIDES_FILE",
                        tmp_path / "health_overrides.json")
    metrics = {"avg_confidence": 0.2, "coverage_pct": 0.4, "bootstrap_loop_risk": 0.8,
               "obs_7d_total": 100, "obs_7d_ai_mediated": 80, "obs_7d_independent": 20}
    neglected = [{"facet_id": f"f{i}", "category": "cognitive", "confidence": 0.1,
                  "observation_count": 1, "recent_independent_obs": 0} for i in range(7)]
    apply_remediation(metrics, neglected, "critical")
    override_file = tmp_path / "health_overrides.json"
    assert override_file.exists()
    data = _json.loads(override_file.read_text())
    assert data["severity"] == "critical"
    assert data["max_questions_per_day"] == 5
    assert len(data["priority_facets"]) == 5
    assert data["loop_warning"] is True


def test_apply_remediation_degraded_sets_4_questions(tmp_path, monkeypatch):
    monkeypatch.setattr("mnemon.relic_health_monitor.HEALTH_OVERRIDES_FILE",
                        tmp_path / "health_overrides.json")
    metrics = {"avg_confidence": 0.32, "coverage_pct": 0.55, "bootstrap_loop_risk": 0.65,
               "obs_7d_total": 50, "obs_7d_ai_mediated": 33, "obs_7d_independent": 17}
    apply_remediation(metrics, [], "degraded")
    data = _json.loads((tmp_path / "health_overrides.json").read_text())
    assert data["max_questions_per_day"] == 4
    assert data["severity"] == "degraded"


def test_apply_remediation_healthy_removes_file(tmp_path, monkeypatch):
    override_file = tmp_path / "health_overrides.json"
    override_file.write_text('{"severity": "critical"}')
    monkeypatch.setattr("mnemon.relic_health_monitor.HEALTH_OVERRIDES_FILE", override_file)
    metrics = {"avg_confidence": 0.6, "coverage_pct": 0.75, "bootstrap_loop_risk": 0.3,
               "obs_7d_total": 50, "obs_7d_ai_mediated": 15, "obs_7d_independent": 35}
    apply_remediation(metrics, [], "healthy")
    assert not override_file.exists()


def test_apply_remediation_healthy_no_file_no_error(tmp_path, monkeypatch):
    override_file = tmp_path / "health_overrides.json"
    monkeypatch.setattr("mnemon.relic_health_monitor.HEALTH_OVERRIDES_FILE", override_file)
    metrics = {"avg_confidence": 0.6, "coverage_pct": 0.75, "bootstrap_loop_risk": 0.3,
               "obs_7d_total": 50, "obs_7d_ai_mediated": 15, "obs_7d_independent": 35}
    apply_remediation(metrics, [], "healthy")  # file non esiste, non deve esplodere
    assert not override_file.exists()
