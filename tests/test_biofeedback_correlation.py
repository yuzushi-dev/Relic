"""Unit tests for relic_biofeedback_correlation."""
import math
import sqlite3
from datetime import date, timedelta

import numpy as np
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from relic.relic_biofeedback_correlation import (
    ALPHA_CORRECTED,
    N_MIN,
    RHO_MIN,
    align_series,
    bootstrap_ci,
    classify,
    effective_n,
    ensure_schema,
    load_biofeedback,
    load_text_observations,
    permutation_pvalue,
    spearman,
)


# ── Spearman ──────────────────────────────────────────────────────────────────

def test_spearman_perfect_positive():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert spearman(x, y) == pytest.approx(1.0)


def test_spearman_perfect_negative():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    assert spearman(x, y) == pytest.approx(-1.0)


def test_spearman_zero():
    # Constant y → zero correlation
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([3.0, 3.0, 3.0, 3.0, 3.0])
    rho = spearman(x, y)
    assert rho == pytest.approx(0.0)


def test_spearman_too_short():
    x = np.array([1.0, 2.0])
    y = np.array([1.0, 2.0])
    assert math.isnan(spearman(x, y))


def test_spearman_monotone_nonlinear():
    # Spearman captures monotone nonlinear relationships
    x = np.array([1.0, 4.0, 9.0, 16.0, 25.0])
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert spearman(x, y) == pytest.approx(1.0)


# ── Classification ────────────────────────────────────────────────────────────

def test_classify_insufficient_data():
    assert classify(0.9, 0.8, 1.0, 0.001, N_MIN - 1, 10.0) == "insufficient_data"


def test_classify_confirmed():
    assert classify(0.6, 0.32, 0.82, ALPHA_CORRECTED * 0.5, N_MIN, N_MIN) == "confirmed"


def test_classify_disconfirmed_near_zero():
    # Large N, tiny rho, non-significant
    assert classify(0.05, -0.15, 0.25, 0.8, 30, 28.0) == "disconfirmed"


def test_classify_inconclusive_medium_effect():
    # Medium effect size but not significant enough
    assert classify(0.25, -0.05, 0.50, 0.3, N_MIN, N_MIN) == "inconclusive"


def test_classify_inconclusive_low_n_eff():
    # Enough N but n_eff too low (high autocorrelation)
    assert classify(0.8, 0.6, 0.95, 0.0001, N_MIN, N_MIN / 2 - 1) == "inconclusive"


def test_classify_confirmed_negative_correlation():
    # Strong negative correlation should be confirmed too
    assert classify(-0.65, -0.85, -0.35, ALPHA_CORRECTED * 0.5, N_MIN, N_MIN) == "confirmed"


# ── Align series ──────────────────────────────────────────────────────────────

def _make_dates(start: str, n: int) -> list[str]:
    d = date.fromisoformat(start)
    return [(d + timedelta(days=i)).isoformat() for i in range(n)]


def test_align_series_lag0():
    dates = _make_dates("2026-03-01", 5)
    bio = {d: float(i) for i, d in enumerate(dates)}
    text = {d: float(i) * 2 for i, d in enumerate(dates)}
    x, y, matched = align_series(bio, text, lag=0)
    assert len(x) == 5
    assert len(y) == 5
    assert matched == dates


def test_align_series_lag1():
    dates = _make_dates("2026-03-01", 6)
    bio = {d: float(i) for i, d in enumerate(dates)}
    # Text has dates shifted by 1 day
    text = {d: float(i) for i, d in enumerate(dates[1:], start=1)}
    x, y, matched = align_series(bio, text, lag=1)
    # bio[day] paired with text[day+1] → matches days 0-4 (text has days 1-5)
    assert len(x) == 5
    assert matched[0] == dates[0]


def test_align_series_partial_overlap():
    bio = {"2026-03-01": 1.0, "2026-03-03": 2.0, "2026-03-05": 3.0}
    text = {"2026-03-01": 0.5, "2026-03-05": 0.8}
    x, y, matched = align_series(bio, text, lag=0)
    assert len(x) == 2
    assert set(matched) == {"2026-03-01", "2026-03-05"}


def test_align_series_no_overlap():
    bio = {"2026-03-01": 1.0}
    text = {"2026-04-01": 0.5}
    x, y, matched = align_series(bio, text, lag=0)
    assert len(x) == 0


# ── Effective N ───────────────────────────────────────────────────────────────

def test_effective_n_uncorrelated():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 30)
    y = rng.normal(0, 1, 30)
    n_eff = effective_n(x, y)
    # Should be close to 30 for uncorrelated white noise
    assert 15 < n_eff <= 30


def test_effective_n_highly_autocorrelated():
    # Strongly autocorrelated series → n_eff < n
    x = np.cumsum(np.ones(30))  # perfect lag-1 autocorrelation
    y = np.cumsum(np.ones(30)) + 1
    n_eff = effective_n(x, y)
    assert n_eff < 30


def test_effective_n_short_series():
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([3.0, 2.0, 1.0])
    assert effective_n(x, y) >= 2.0


# ── Permutation p-value ───────────────────────────────────────────────────────

def test_permutation_pvalue_high_for_no_correlation():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 20)
    y = rng.normal(0, 1, 20)
    rho = spearman(x, y)
    p = permutation_pvalue(x, y, rho, n_perm=500, seed=1)
    # Random data → p should be large (not significant)
    assert p > 0.05


def test_permutation_pvalue_low_for_strong_correlation():
    x = np.arange(20, dtype=float)
    y = np.arange(20, dtype=float) + 0.1  # near-perfect monotone
    rho = spearman(x, y)
    p = permutation_pvalue(x, y, rho, n_perm=500, seed=0)
    assert p < 0.01


# ── Bootstrap CI ─────────────────────────────────────────────────────────────

def test_bootstrap_ci_strong_correlation():
    x = np.arange(20, dtype=float)
    y = np.arange(20, dtype=float)
    lo, hi = bootstrap_ci(x, y, n_boot=200, seed=42)
    assert lo > 0.8
    assert hi <= 1.0


def test_bootstrap_ci_contains_zero_for_noise():
    rng = np.random.default_rng(7)
    x = rng.normal(0, 1, 20)
    y = rng.normal(0, 1, 20)
    lo, hi = bootstrap_ci(x, y, n_boot=500, seed=7)
    assert lo < 0 < hi  # CI crosses zero for unrelated series


# ── DB integration ────────────────────────────────────────────────────────────

def _make_test_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE biofeedback_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'test',
            signal_type TEXT NOT NULL,
            value REAL,
            unit TEXT,
            metadata_json TEXT,
            pulled_at TEXT NOT NULL,
            UNIQUE(date, signal_type)
        );
        CREATE TABLE observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facet_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_ref TEXT,
            content TEXT,
            extracted_signal TEXT,
            signal_strength REAL,
            signal_position REAL,
            context TEXT,
            created_at TEXT NOT NULL,
            context_metadata TEXT,
            conversation_domain TEXT
        );
        CREATE TABLE inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            from_id TEXT,
            content TEXT,
            channel_id TEXT,
            received_at TEXT,
            processed INTEGER DEFAULT 0,
            processed_at TEXT
        );
    """)
    return db


def test_ensure_schema_creates_tables():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    ensure_schema(db)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "biofeedback_correlations" in tables
    assert "biofeedback_correlation_readiness" in tables


def test_load_biofeedback_returns_dict():
    db = _make_test_db()
    db.execute("INSERT INTO biofeedback_readings (date, signal_type, value, pulled_at) VALUES ('2026-03-01','hrv_rmssd',42.0,'2026-03-02')")
    db.execute("INSERT INTO biofeedback_readings (date, signal_type, value, pulled_at) VALUES ('2026-03-02','hrv_rmssd',38.5,'2026-03-03')")
    db.commit()
    result = load_biofeedback(db, "hrv_rmssd")
    assert result == {"2026-03-01": 42.0, "2026-03-02": 38.5}


def test_load_biofeedback_excludes_null():
    db = _make_test_db()
    db.execute("INSERT INTO biofeedback_readings (date, signal_type, value, pulled_at) VALUES ('2026-03-01','hrv_rmssd',NULL,'2026-03-02')")
    db.commit()
    result = load_biofeedback(db, "hrv_rmssd")
    assert result == {}


def test_load_text_observations_weighted_mean():
    db = _make_test_db()
    db.execute(
        "INSERT INTO observations (facet_id, source_type, signal_position, signal_strength, created_at) "
        "VALUES ('emotional.resilience_pattern', 'passive_chat', 0.8, 0.6, '2026-03-01T10:00:00')"
    )
    db.execute(
        "INSERT INTO observations (facet_id, source_type, signal_position, signal_strength, created_at) "
        "VALUES ('emotional.resilience_pattern', 'passive_chat', 0.4, 0.4, '2026-03-01T14:00:00')"
    )
    db.commit()
    result = load_text_observations(db, "emotional.resilience_pattern")
    # weighted mean: (0.8*0.6 + 0.4*0.4) / (0.6+0.4) = (0.48+0.16)/1.0 = 0.64
    assert result["2026-03-01"] == pytest.approx(0.64)


def test_load_text_observations_excludes_biofeedback_source():
    db = _make_test_db()
    db.execute(
        "INSERT INTO observations (facet_id, source_type, signal_position, signal_strength, created_at) "
        "VALUES ('emotional.resilience_pattern', 'biofeedback', 0.9, 0.9, '2026-03-01T10:00:00')"
    )
    db.commit()
    result = load_text_observations(db, "emotional.resilience_pattern")
    assert result == {}


def test_load_text_observations_excludes_biofeedback_correlation_source():
    db = _make_test_db()
    db.execute(
        "INSERT INTO observations (facet_id, source_type, signal_position, signal_strength, created_at) "
        "VALUES ('emotional.resilience_pattern', 'biofeedback_correlation', 0.9, 0.9, '2026-03-01T10:00:00')"
    )
    db.commit()
    result = load_text_observations(db, "emotional.resilience_pattern")
    assert result == {}
