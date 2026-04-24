#!/usr/bin/env python3
"""Relic Biofeedback Correlation Engine.

Computes Spearman rank correlations between physiological signals
(biofeedback_readings) and personality facet observations derived from text
(observations table, non-biofeedback sources), at lag-0 and lag-1 offsets.

Statistical approach:
  - Spearman rank correlation (non-parametric, robust on short series)
  - Permutation p-value (1000 resamples, no scipy required)
  - Bootstrap 95% CI (1000 resamples)
  - Effective N correction for autocorrelation (Dutilleul 1993 proxy)
  - Bonferroni family-wise error rate correction

Scientific grounding: Appelhans & Luecken (2006), Thayer & Lane (2009),
Castaldo et al. (2023).

Usage:
  python3 -m relic.biofeedback_correlation [--dry-run]
"""
from __future__ import annotations

import math
import os
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import numpy as np
import requests

from lib.log import info, warn

SCRIPT = "relic_biofeedback_corr"

# ── Config ────────────────────────────────────────────────────────────────────

def _data_dir() -> Path:
    env = os.environ.get("RELIC_DATA_DIR", "")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "runtime"


DB_PATH = _data_dir() / "relic.db"

N_MIN = 14               # minimum aligned pairs to compute a correlation
RHO_MIN = 0.30           # minimum effect size (practical significance)
ALPHA = 0.05             # family-wise error rate before Bonferroni correction
BOOTSTRAP_N = 1000
PERMUTATION_N = 1000
LAGS = [0, 1]            # lag-0: same day; lag-1: bio predicts next-day behavior
DIVERGENCE_THRESHOLD = 0.5  # |bio_pos - text_pos| to flag bio-linguistic divergence
MESSAGE_SAMPLE_N = 3        # inbox messages attached to divergence report

_TG_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_TG_CHAT_ID   = os.environ.get("RELIC_CORR_TELEGRAM_CHAT_ID", "")
_TG_THREAD_ID = os.environ.get("RELIC_CORR_TELEGRAM_THREAD_ID", "")

# Signal → theoretically predicted facet (non-None mappings from FACET_MAP)
SIGNAL_FACET_MAP: dict[str, str] = {
    "hrv_rmssd":               "emotional.resilience_pattern",
    "sleep_deep_pct":          "emotional.distress_tolerance",
    "sleep_rem_pct":           "emotional.emotion_clarity",
    "sleep_onset_ts":          "temporal.planning_horizon",
    "sleep_score":             "emotional.distress_tolerance",
    "pai_score":               "temporal.routine_attachment",
    "stress_avg":              "temporal.impulsivity_regulation",
    "sleep_rr":                "emotional.stress_response",
    "sleep_stages_efficiency": "emotional.distress_tolerance",
    "sleep_efficiency":        "emotional.distress_tolerance",
    "circadian_regularity":    "temporal.routine_attachment",
    "recovery_score":          "emotional.resilience_pattern",
    "hr_reactivity":           "emotional.emotional_expression",
    "activity_consistency":    "temporal.routine_attachment",
    "eeg_focus_score":         "cognitive.analytical_approach",
    "eeg_calm_score":          "emotional.distress_tolerance",
    "eeg_theta_beta_ratio":    "cognitive.decision_speed",
    "eeg_frontal_asymmetry":   "emotional.emotional_expression",
    "eeg_engagement":          "cognitive.information_gathering",
    "eeg_alpha_variability":   "meta_cognition.reflection_habit",
    "eeg_meditation_depth":    "emotional.resilience_pattern",
}

# Total Bonferroni comparisons
N_COMPARISONS = len(SIGNAL_FACET_MAP) * len(LAGS)
ALPHA_CORRECTED = ALPHA / N_COMPARISONS

# Source types excluded from text observations (prevents circular correlation)
_BIOFEEDBACK_SOURCES = frozenset({"biofeedback", "biofeedback_correlation"})

# ── DB ────────────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS biofeedback_correlations (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_type      TEXT    NOT NULL,
            facet_id         TEXT    NOT NULL,
            lag_days         INTEGER NOT NULL,
            n_pairs          INTEGER NOT NULL,
            n_eff            REAL    NOT NULL,
            rho              REAL    NOT NULL,
            rho_ci_low       REAL    NOT NULL,
            rho_ci_high      REAL    NOT NULL,
            p_value          REAL    NOT NULL,
            correlation_status TEXT  NOT NULL,
            window_start     TEXT    NOT NULL,
            window_end       TEXT    NOT NULL,
            previous_status  TEXT,
            computed_at      TEXT    NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_biofeedback_corr_key
            ON biofeedback_correlations(signal_type, facet_id, lag_days);

        CREATE TABLE IF NOT EXISTS biofeedback_correlation_readiness (
            signal_type  TEXT    NOT NULL,
            facet_id     TEXT    NOT NULL,
            lag_days     INTEGER NOT NULL,
            n_available  INTEGER NOT NULL,
            last_updated TEXT    NOT NULL,
            PRIMARY KEY (signal_type, facet_id, lag_days)
        );
    """)
    db.commit()

# ── Data loading ──────────────────────────────────────────────────────────────

def load_biofeedback(db: sqlite3.Connection, signal_type: str) -> dict[str, float]:
    rows = db.execute(
        "SELECT date, value FROM biofeedback_readings "
        "WHERE signal_type=? AND value IS NOT NULL ORDER BY date",
        (signal_type,),
    ).fetchall()
    return {r["date"]: r["value"] for r in rows}


def load_text_observations(db: sqlite3.Connection, facet_id: str) -> dict[str, float]:
    """Return {date_str: weighted_mean_signal_position} for text-only observations.

    Excludes biofeedback and biofeedback_correlation sources to prevent
    circular correlation between the two channels.
    """
    placeholders = ",".join("?" * len(_BIOFEEDBACK_SOURCES))
    rows = db.execute(
        f"""SELECT DATE(created_at) as obs_date,
                   signal_position,
                   signal_strength
            FROM observations
            WHERE facet_id=?
              AND source_type NOT IN ({placeholders})
              AND signal_position IS NOT NULL
              AND signal_strength IS NOT NULL
            ORDER BY obs_date""",
        (facet_id, *_BIOFEEDBACK_SOURCES),
    ).fetchall()

    by_day: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        by_day[r["obs_date"]].append((r["signal_position"], r["signal_strength"]))

    result: dict[str, float] = {}
    for day, pairs in by_day.items():
        total_w = sum(w for _, w in pairs)
        if total_w > 0:
            result[day] = sum(pos * w for pos, w in pairs) / total_w
    return result


def align_series(
    bio: dict[str, float],
    text: dict[str, float],
    lag: int,
) -> tuple[list[float], list[float], list[str]]:
    """Align bio and text series at the given lag.

    lag=0: biofeedback date == observation date (same day)
    lag=1: observation date == biofeedback date + 1 day (predictive)
    """
    x_vals, y_vals, dates = [], [], []
    for bio_date_str, bio_val in sorted(bio.items()):
        obs_date = (date.fromisoformat(bio_date_str) + timedelta(days=lag)).isoformat()
        if obs_date in text:
            x_vals.append(bio_val)
            y_vals.append(text[obs_date])
            dates.append(bio_date_str)
    return x_vals, y_vals, dates

# ── Statistics ────────────────────────────────────────────────────────────────

def _rank_with_ties(x: np.ndarray) -> np.ndarray:
    """Ranks with average-tie handling (1-indexed)."""
    n = len(x)
    order = np.argsort(x, kind="stable")
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation with proper tie handling via Pearson on ranks."""
    n = len(x)
    if n < 3:
        return float("nan")
    rx = _rank_with_ties(x)
    ry = _rank_with_ties(y)
    rx_c = rx - rx.mean()
    ry_c = ry - ry.mean()
    denom = math.sqrt(float(np.sum(rx_c ** 2) * np.sum(ry_c ** 2)))
    if denom == 0.0:
        return 0.0  # constant series → undefined, treated as no correlation
    return float(np.sum(rx_c * ry_c) / denom)


def permutation_pvalue(
    x: np.ndarray, y: np.ndarray, rho_obs: float,
    n_perm: int = PERMUTATION_N, seed: int = 42,
) -> float:
    """Two-tailed permutation p-value for Spearman ρ."""
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n_perm):
        rho_perm = spearman(x, rng.permutation(y))
        if abs(rho_perm) >= abs(rho_obs):
            count += 1
    return (count + 1) / (n_perm + 1)


def bootstrap_ci(
    x: np.ndarray, y: np.ndarray,
    n_boot: int = BOOTSTRAP_N, seed: int = 42,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(x)
    rhos: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        rhos.append(spearman(x[idx], y[idx]))
    arr = np.array(rhos)
    return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def effective_n(x: np.ndarray, y: np.ndarray) -> float:
    """Effective N corrected for lag-1 autocorrelation (Dutilleul 1993 proxy)."""
    n = len(x)
    if n < 4:
        return float(n)
    r1x = float(np.corrcoef(x[:-1], x[1:])[0, 1]) if n > 2 else 0.0
    r1y = float(np.corrcoef(y[:-1], y[1:])[0, 1]) if n > 2 else 0.0
    if math.isnan(r1x):
        r1x = 0.0
    if math.isnan(r1y):
        r1y = 0.0
    denom = 1.0 + r1x * r1y
    return max(2.0, n * (1.0 - r1x * r1y) / denom) if denom != 0 else float(n)


def classify(
    rho: float, ci_low: float, ci_high: float,
    p_corrected: float, n: int, n_eff: float,
) -> str:
    """Classify a correlation result into one of four statuses.

    Conservative by design: prefers 'inconclusive' over speculative conclusions.
    """
    if n < N_MIN:
        return "insufficient_data"
    if n_eff < N_MIN / 2:
        # Too much autocorrelation — effective degrees of freedom too low
        return "inconclusive"
    significant = p_corrected < ALPHA_CORRECTED
    strong_effect = abs(rho) >= RHO_MIN
    ci_consistent = (rho > 0 and ci_low > 0) or (rho < 0 and ci_high < 0)
    if significant and strong_effect and ci_consistent:
        return "confirmed"
    # Disconfirmation: adequate N AND practically zero observed effect
    if abs(rho) < 0.15:
        return "disconfirmed"
    return "inconclusive"

# ── Divergence detection ──────────────────────────────────────────────────────

class Divergence(NamedTuple):
    date: str
    signal_type: str
    facet_id: str
    bio_position: float
    text_position: float
    delta: float
    sample_messages: list[str]


def detect_divergences(
    db: sqlite3.Connection,
    bio_by_signal: dict[str, dict[str, float]],
    text_by_facet: dict[str, dict[str, float]],
) -> list[Divergence]:
    """Find days where biofeedback and text observations for the same facet diverge.

    Divergence = |biofeedback_obs_position - text_weighted_position| >= threshold.
    Attaches a sample of inbox messages from that day for human disambiguation.
    """
    divergences: list[Divergence] = []
    for signal_type, facet_id in SIGNAL_FACET_MAP.items():
        bio = bio_by_signal.get(signal_type, {})
        text = text_by_facet.get(facet_id, {})
        for day in sorted(bio):
            bio_obs = db.execute(
                "SELECT signal_position FROM observations "
                "WHERE source_type='biofeedback' AND source_ref=? LIMIT 1",
                (f"biofeedback:{day}:{signal_type}",),
            ).fetchone()
            if not bio_obs:
                continue
            bio_pos = bio_obs["signal_position"]
            text_pos = text.get(day)
            if text_pos is None:
                continue
            delta = abs(bio_pos - text_pos)
            if delta >= DIVERGENCE_THRESHOLD:
                msgs = _sample_messages(db, day)
                divergences.append(Divergence(
                    date=day, signal_type=signal_type, facet_id=facet_id,
                    bio_position=bio_pos, text_position=text_pos,
                    delta=delta, sample_messages=msgs,
                ))
    return divergences


def _sample_messages(db: sqlite3.Connection, day: str, n: int = MESSAGE_SAMPLE_N) -> list[str]:
    rows = db.execute(
        """SELECT content FROM inbox
           WHERE DATE(received_at)=?
             AND content IS NOT NULL
             AND length(content) > 20
           ORDER BY RANDOM() LIMIT ?""",
        (day, n),
    ).fetchall()
    return [r["content"][:200] for r in rows]

# ── Storage ───────────────────────────────────────────────────────────────────

def _upsert_correlation(
    db: sqlite3.Connection,
    signal_type: str, facet_id: str, lag: int,
    n: int, n_eff: float, rho: float,
    ci_low: float, ci_high: float, p_val: float,
    status: str, window_start: str, window_end: str,
) -> str | None:
    """Upsert result; returns previous status if the status changed."""
    existing = db.execute(
        "SELECT correlation_status FROM biofeedback_correlations "
        "WHERE signal_type=? AND facet_id=? AND lag_days=?",
        (signal_type, facet_id, lag),
    ).fetchone()
    prev = existing["correlation_status"] if existing else None
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO biofeedback_correlations
           (signal_type, facet_id, lag_days, n_pairs, n_eff, rho,
            rho_ci_low, rho_ci_high, p_value, correlation_status,
            window_start, window_end, previous_status, computed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(signal_type, facet_id, lag_days) DO UPDATE SET
             n_pairs=excluded.n_pairs,
             n_eff=excluded.n_eff,
             rho=excluded.rho,
             rho_ci_low=excluded.rho_ci_low,
             rho_ci_high=excluded.rho_ci_high,
             p_value=excluded.p_value,
             correlation_status=excluded.correlation_status,
             window_start=excluded.window_start,
             window_end=excluded.window_end,
             previous_status=excluded.previous_status,
             computed_at=excluded.computed_at""",
        (signal_type, facet_id, lag, n, round(n_eff, 1), round(rho, 4),
         round(ci_low, 4), round(ci_high, 4), round(p_val, 6),
         status, window_start, window_end, prev, now),
    )
    return prev if prev != status else None


def _upsert_readiness(
    db: sqlite3.Connection, signal_type: str, facet_id: str, lag: int, n: int,
) -> None:
    db.execute(
        """INSERT INTO biofeedback_correlation_readiness
           (signal_type, facet_id, lag_days, n_available, last_updated)
           VALUES (?,?,?,?,?)
           ON CONFLICT(signal_type, facet_id, lag_days) DO UPDATE SET
             n_available=excluded.n_available,
             last_updated=excluded.last_updated""",
        (signal_type, facet_id, lag, n, datetime.now(timezone.utc).isoformat()),
    )

# ── Telegram ──────────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    if not _TG_TOKEN or not _TG_CHAT_ID:
        warn(SCRIPT, "telegram_skip", reason="RELIC_CORR_TELEGRAM_CHAT_ID or BOT_TOKEN not set")
        return
    payload: dict = {"chat_id": _TG_CHAT_ID, "text": text[:4000], "parse_mode": "Markdown"}
    if _TG_THREAD_ID:
        payload["message_thread_id"] = int(_TG_THREAD_ID)
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            json=payload, timeout=15,
        )
        r.raise_for_status()
    except Exception as exc:
        warn(SCRIPT, "telegram_error", error=str(exc))


def _format_report(
    results: list[dict],
    divergences: list[Divergence],
    status_changes: list[tuple[str, str, int, str, str]],
    newly_unlocked: list[tuple[str, str, int]],
) -> str:
    confirmed    = [r for r in results if r["status"] == "confirmed"]
    disconfirmed = [r for r in results if r["status"] == "disconfirmed"]
    inconclusive = [r for r in results if r["status"] == "inconclusive"]
    insufficient = [r for r in results if r["status"] == "insufficient_data"]

    lines = [
        "*Biofeedback Correlation Report*",
        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "",
        (f"Coppie analizzate: {len(results)} | "
         f"Confermate: {len(confirmed)} | "
         f"Disconfermate: {len(disconfirmed)} | "
         f"Inconcludenti: {len(inconclusive)} | "
         f"Dati insufficienti: {len(insufficient)}"),
    ]

    if status_changes:
        lines += ["", "*Cambiamenti di stato*"]
        for sig, fac, lag, prev, curr in status_changes:
            lines.append(f"  {sig} → {fac} (lag={lag}d): `{prev}` → `{curr}`")

    if newly_unlocked:
        lines += ["", "*Coppie appena sbloccate (N ≥ 14)*"]
        for sig, fac, lag in newly_unlocked:
            lines.append(f"  {sig} → {fac} (lag={lag}d)")

    if confirmed:
        lines += ["", "*Correlazioni confermate*"]
        for r in confirmed:
            lines.append(
                f"  {r['signal']} → {r['facet']} (lag={r['lag']}d) "
                f"ρ={r['rho']:+.2f} [{r['ci_low']:+.2f}, {r['ci_high']:+.2f}] "
                f"N={r['n']} N_eff={r.get('n_eff', '?'):.1f}"
            )

    if disconfirmed:
        lines += ["", "*Correlazioni assenti*"]
        for r in disconfirmed:
            lines.append(
                f"  {r['signal']} → {r['facet']} (lag={r['lag']}d) "
                f"ρ={r['rho']:+.2f} N={r['n']} — nessuna relazione rilevata"
            )

    if divergences:
        lines += ["", "*Divergenze bio-linguistiche*"]
        for d in divergences[:5]:
            s_bio = "+" if d.bio_position >= 0 else ""
            s_txt = "+" if d.text_position >= 0 else ""
            lines.append(
                f"  {d.date} | {d.signal_type} → {d.facet_id}\n"
                f"    bio={s_bio}{d.bio_position:.2f}  testo={s_txt}{d.text_position:.2f}  Δ={d.delta:.2f}"
            )
            if d.sample_messages:
                lines.append("    Messaggi campione:")
                for msg in d.sample_messages:
                    lines.append(f"    › {msg[:120]}")

    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> None:
    db = get_db()
    ensure_schema(db)

    bio_by_signal: dict[str, dict[str, float]] = {
        sig: load_biofeedback(db, sig) for sig in SIGNAL_FACET_MAP
    }
    text_by_facet: dict[str, dict[str, float]] = {
        fac: load_text_observations(db, fac)
        for fac in set(SIGNAL_FACET_MAP.values())
    }

    prev_readiness: dict[tuple, int] = {
        (r["signal_type"], r["facet_id"], r["lag_days"]): r["n_available"]
        for r in db.execute(
            "SELECT signal_type, facet_id, lag_days, n_available "
            "FROM biofeedback_correlation_readiness"
        ).fetchall()
    }

    results: list[dict] = []
    status_changes: list[tuple] = []
    newly_unlocked: list[tuple] = []

    for signal_type, facet_id in SIGNAL_FACET_MAP.items():
        bio = bio_by_signal[signal_type]
        text = text_by_facet[facet_id]

        for lag in LAGS:
            x_list, y_list, dates = align_series(bio, text, lag)
            n = len(x_list)

            if not dry_run:
                _upsert_readiness(db, signal_type, facet_id, lag, n)

            prev_n = prev_readiness.get((signal_type, facet_id, lag), 0)
            if prev_n < N_MIN <= n:
                newly_unlocked.append((signal_type, facet_id, lag))

            if n < N_MIN:
                rec = {"signal": signal_type, "facet": facet_id, "lag": lag,
                       "n": n, "status": "insufficient_data",
                       "rho": 0.0, "ci_low": 0.0, "ci_high": 0.0, "p": 1.0}
                results.append(rec)
                if not dry_run:
                    _upsert_correlation(
                        db, signal_type, facet_id, lag, n, float(n),
                        0.0, 0.0, 0.0, 1.0, "insufficient_data",
                        "", "",
                    )
                continue

            x = np.array(x_list)
            y = np.array(y_list)

            rho = spearman(x, y)
            p_raw = permutation_pvalue(x, y, rho)
            p_corrected = min(1.0, p_raw * N_COMPARISONS)
            ci_low, ci_high = bootstrap_ci(x, y)
            n_eff = effective_n(x, y)
            status = classify(rho, ci_low, ci_high, p_corrected, n, n_eff)

            info(SCRIPT,
                 f"{signal_type}→{facet_id} lag={lag} "
                 f"ρ={rho:.3f} p_corr={p_corrected:.4f} "
                 f"N={n} N_eff={n_eff:.1f} → {status}")

            rec = {
                "signal": signal_type, "facet": facet_id, "lag": lag,
                "n": n, "n_eff": n_eff, "status": status,
                "rho": rho, "ci_low": ci_low, "ci_high": ci_high, "p": p_corrected,
            }
            results.append(rec)

            if not dry_run:
                prev_status = _upsert_correlation(
                    db, signal_type, facet_id, lag, n, n_eff, rho,
                    ci_low, ci_high, p_corrected, status,
                    dates[0], dates[-1],
                )
                if prev_status and prev_status != status:
                    status_changes.append((signal_type, facet_id, lag, prev_status, status))

    divergences = detect_divergences(db, bio_by_signal, text_by_facet)

    if not dry_run:
        db.commit()
    db.close()

    report = _format_report(results, divergences, status_changes, newly_unlocked)
    info(SCRIPT, f"report: {len(results)} pairs, {len(divergences)} divergences")

    if dry_run:
        print(report)
    else:
        _send_telegram(report)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Relic Biofeedback Correlation Engine")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute and print report without writing or sending")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
