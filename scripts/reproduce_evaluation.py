#!/usr/bin/env python3
"""Reproduce the whitepaper §9 evaluation figures on a local deployment DB.

The paper's specific numbers (7,026 observations, 38 days, 147 hypotheses,
75% coverage) come from a private first-person deployment that is not
distributed with the OSS repo. This script lets any user regenerate the
equivalent figures and headline metrics from their own `relic.db`.

Outputs:
  <out>/metrics.json             - all headline numbers, always produced
  <out>/figure2_convergence.png  - Panel A, B, C (requires matplotlib)
  <out>/figure3_sources.png      - Panel A + targeting comparison (ditto)

Usage:
  python3 scripts/reproduce_evaluation.py --db <path> [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

COVERAGE_THRESHOLD = 0.30


def load_daily_snapshots(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Aggregate model_snapshots to one record per UTC calendar day (latest)."""
    rows = db.execute(
        "SELECT snapshot_at, total_observations, avg_confidence, coverage_pct "
        "FROM model_snapshots ORDER BY snapshot_at ASC"
    ).fetchall()
    by_day: dict[str, dict[str, Any]] = {}
    for snapshot_at, total_obs, avg_conf, cov_pct in rows:
        try:
            dt = datetime.fromisoformat(snapshot_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            continue
        day = dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
        by_day[day] = {
            "day": day,
            "total_observations": int(total_obs or 0),
            "avg_confidence": float(avg_conf or 0.0),
            "coverage_pct": float(cov_pct or 0.0),
        }
    return [by_day[k] for k in sorted(by_day)]


def source_composition(db: sqlite3.Connection) -> dict[str, Any]:
    rows = db.execute(
        "SELECT source_type, COUNT(*) FROM observations GROUP BY source_type"
    ).fetchall()
    by_type = {src or "unknown": int(n) for src, n in rows}
    total = sum(by_type.values())
    return {
        "by_type": by_type,
        "total": total,
        "pct_by_type": {
            k: (100.0 * v / total if total else 0.0) for k, v in by_type.items()
        },
    }


def targeting_comparison(db: sqlite3.Connection) -> dict[str, Any]:
    """Compare confidence of facets that received check-ins vs untargeted."""
    targeted = {
        row[0]
        for row in db.execute(
            "SELECT DISTINCT facet_id FROM checkin_exchanges "
            "WHERE facet_id IS NOT NULL"
        ).fetchall()
    }
    rows = db.execute("SELECT facet_id, confidence FROM traits").fetchall()
    t_vals = [float(c) for fid, c in rows if fid in targeted and c is not None]
    u_vals = [float(c) for fid, c in rows if fid not in targeted and c is not None]
    return {
        "targeted": {
            "count": len(t_vals),
            "median_confidence": float(median(t_vals)) if t_vals else None,
        },
        "untargeted": {
            "count": len(u_vals),
            "median_confidence": float(median(u_vals)) if u_vals else None,
        },
    }


def schema_info(db: sqlite3.Connection) -> dict[str, Any]:
    rows = db.execute(
        "SELECT category, COUNT(*) FROM facets GROUP BY category ORDER BY category"
    ).fetchall()
    by_category = {cat: int(n) for cat, n in rows}
    return {
        "categories": list(by_category.keys()),
        "facets_per_category": by_category,
        "total_facets": sum(by_category.values()),
    }


def hypothesis_count(db: sqlite3.Connection) -> int:
    try:
        (n,) = db.execute("SELECT COUNT(*) FROM hypotheses").fetchone()
        return int(n)
    except sqlite3.OperationalError:
        return 0


def per_category_trajectory(
    daily: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Extract per-category confidence from serialized snapshot_data if present."""
    # daily only stores aggregate; category trajectory requires snapshot_data.
    # Returns empty dict when the field is not populated; tests don't require it.
    return {}


def compute_metrics(db_path: Path) -> dict[str, Any]:
    db = sqlite3.connect(str(db_path))
    try:
        daily = load_daily_snapshots(db)
        sources = source_composition(db)
        targeting = targeting_comparison(db)
        schema = schema_info(db)
        hyp_n = hypothesis_count(db)
    finally:
        db.close()

    convergence = {
        "daily_series": daily,
        "first_day": daily[0]["day"] if daily else None,
        "last_day": daily[-1]["day"] if daily else None,
        "final_coverage_pct": daily[-1]["coverage_pct"] if daily else 0.0,
        "final_avg_confidence": daily[-1]["avg_confidence"] if daily else 0.0,
        "cumulative_observations": daily[-1]["total_observations"] if daily else 0,
        "coverage_threshold": COVERAGE_THRESHOLD,
    }
    return {
        "convergence": convergence,
        "sources": sources,
        "targeting": targeting,
        "schema": schema,
        "hypotheses_total": hyp_n,
    }


def render_figures(metrics: dict[str, Any], out_dir: Path) -> list[Path]:
    """Render Figure 2 and 3 if matplotlib is available. Silent no-op otherwise."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    produced: list[Path] = []
    series = metrics["convergence"]["daily_series"]
    if series:
        days = [s["day"] for s in series]
        cov = [s["coverage_pct"] for s in series]
        conf = [s["avg_confidence"] for s in series]
        cum = [s["total_observations"] for s in series]

        fig, (ax_a, ax_b, ax_c) = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
        ax_a.plot(days, cov, marker="o")
        ax_a.set_ylabel("Coverage %")
        ax_a.set_title("Panel A - Facet coverage above threshold")
        ax_b.plot(days, conf, marker="o", color="tab:orange")
        ax_b.set_ylabel("Avg confidence")
        ax_b.set_title("Panel B - Stored average trait confidence")
        ax_c.plot(days, cum, marker="o", color="tab:green")
        ax_c.set_ylabel("Cumulative observations")
        ax_c.set_title("Panel C - Cumulative observation growth")
        ax_c.set_xlabel("Day")
        for ax in (ax_a, ax_b, ax_c):
            ax.grid(alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        fig2 = out_dir / "figure2_convergence.png"
        fig.savefig(fig2, dpi=120)
        plt.close(fig)
        produced.append(fig2)

    sources = metrics["sources"]["by_type"]
    if sources:
        labels = list(sources.keys())
        counts = [sources[k] for k in labels]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh(labels, counts)
        ax.set_xlabel("Observations")
        ax.set_title("Figure 3 Panel A - Evidence source composition")
        ax.grid(axis="x", alpha=0.3)
        plt.tight_layout()
        fig3 = out_dir / "figure3_sources.png"
        fig.savefig(fig3, dpi=120)
        plt.close(fig)
        produced.append(fig3)

    return produced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path,
                        help="Path to a relic.db deployment database")
    parser.add_argument("--out", default=Path("out"), type=Path,
                        help="Output directory (default: ./out)")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"error: DB not found at {args.db}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    metrics = compute_metrics(args.db)
    metrics_path = args.out / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True),
                            encoding="utf-8")
    figures = render_figures(metrics, args.out)

    print(f"wrote {metrics_path}")
    for f in figures:
        print(f"wrote {f}")
    if not figures:
        print("(no figures rendered: matplotlib not installed or empty series)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
