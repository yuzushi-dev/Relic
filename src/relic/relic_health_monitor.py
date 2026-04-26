#!/usr/bin/env python3
"""Relic Health Monitor — Paperclip verification layer for model health.

Cron entrypoint: relic:health-monitor
Schedule: 0 */12 * * *  (every 12 hours)

Computes model health metrics (avg_confidence, coverage, bootstrap_loop_risk),
identifies neglected facets, and submits a structured health issue to the
Paperclip orchestration layer for review by the health_strategist agent.

Gracefully skips if Paperclip env vars are not configured.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lib.relic_debate import run_debate
from lib.reviewer_workspace import export_debate

SCRIPT = "relic_health_monitor"

RELIC_DIR = Path(os.environ.get("RELIC_DATA_DIR") or str(Path(__file__).resolve().parents[1] / "relic"))
DB_PATH = RELIC_DIR / "relic.db"

# Thresholds
COVERAGE_WARN = 0.60       # facets above 0.3 confidence — warn if below 60%
COVERAGE_CRIT = 0.45
AVG_CONF_WARN = 0.35
AVG_CONF_CRIT = 0.25
LOOP_RISK_WARN = 0.60
LOOP_RISK_CRIT = 0.75
NEGLECTED_CONF = 0.25      # facet classified as neglected if confidence below this
NEGLECTED_DAYS = 14        # and no checkin observation in last N days


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(level: str, event: str, **kv: Any) -> None:
    payload = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
               "script": SCRIPT, "event": event, **kv}
    print(json.dumps(payload), flush=True)


def info(event: str, **kv: Any) -> None:
    _log("INFO", event, **kv)


def warn(event: str, **kv: Any) -> None:
    _log("WARN", event, **kv)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def compute_metrics(db: sqlite3.Connection) -> dict[str, Any]:
    """Compute current model health metrics from the DB."""
    # Avg confidence and coverage
    rows = db.execute(
        "SELECT t.facet_id, t.confidence, t.observation_count, f.category "
        "FROM traits t JOIN facets f ON t.facet_id = f.id"
    ).fetchall()

    if not rows:
        return {"error": "no_traits"}

    confidences = [r["confidence"] for r in rows if r["confidence"] is not None]
    covered = sum(1 for c in confidences if c >= 0.30)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    coverage_pct = covered / len(confidences) if confidences else 0.0

    # Bootstrap loop risk (7-day window, same logic as relic_healthcheck IMP-14)
    cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    loop_row = db.execute(
        """SELECT COUNT(*) as total,
                  SUM(CASE WHEN source_type='session_behavioral' THEN 1 ELSE 0 END) as ai_med
           FROM observations WHERE created_at >= ?""",
        (cutoff_7d,),
    ).fetchone()
    total_7d = loop_row["total"] or 0
    ai_med_7d = loop_row["ai_med"] or 0
    loop_risk = (ai_med_7d / total_7d) if total_7d > 0 else 0.0

    # Independent (non-session_behavioral) coverage in last 7 days
    independent_7d = total_7d - ai_med_7d

    return {
        "avg_confidence": round(avg_confidence, 4),
        "coverage_pct": round(coverage_pct, 4),
        "facets_total": len(confidences),
        "facets_covered": covered,
        "bootstrap_loop_risk": round(loop_risk, 4),
        "obs_7d_total": total_7d,
        "obs_7d_ai_mediated": ai_med_7d,
        "obs_7d_independent": independent_7d,
    }


def find_neglected_facets(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return facets with low confidence and no recent independent observations."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=NEGLECTED_DAYS)).isoformat()
    rows = db.execute(
        """SELECT t.facet_id, t.confidence, t.observation_count, f.category,
                  t.last_synthesis_at
           FROM traits t JOIN facets f ON t.facet_id = f.id
           WHERE t.confidence < ?
           ORDER BY t.confidence ASC""",
        (NEGLECTED_CONF,),
    ).fetchall()

    neglected = []
    for r in rows:
        # Check if there are independent observations in the last NEGLECTED_DAYS
        recent = db.execute(
            """SELECT COUNT(*) as c FROM observations
               WHERE facet_id = ? AND source_type != 'session_behavioral'
               AND created_at >= ?""",
            (r["facet_id"], cutoff),
        ).fetchone()["c"]
        neglected.append({
            "facet_id": r["facet_id"],
            "category": r["category"],
            "confidence": round(r["confidence"] or 0.0, 4),
            "observation_count": r["observation_count"] or 0,
            "recent_independent_obs": recent,
        })

    # Sort: worst first, then fewest independent obs
    neglected.sort(key=lambda x: (x["confidence"], -x["recent_independent_obs"]))
    return neglected[:20]


def score_severity(metrics: dict[str, Any]) -> str:
    """Return 'critical', 'degraded', or 'healthy'."""
    cov = metrics.get("coverage_pct", 1.0)
    conf = metrics.get("avg_confidence", 1.0)
    loop = metrics.get("bootstrap_loop_risk", 0.0)

    if cov < COVERAGE_CRIT or conf < AVG_CONF_CRIT or loop > LOOP_RISK_CRIT:
        return "critical"
    if cov < COVERAGE_WARN or conf < AVG_CONF_WARN or loop > LOOP_RISK_WARN:
        return "degraded"
    return "healthy"


# ── Report formatting ─────────────────────────────────────────────────────────

def _fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _status_icon(severity: str) -> str:
    return {"critical": "CRITICAL", "degraded": "DEGRADED", "healthy": "OK"}[severity]


def format_report(metrics: dict[str, Any], neglected: list[dict[str, Any]],
                  severity: str) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    lines = [
        f"## Relic Health Monitor — {today}",
        f"**Status**: {_status_icon(severity)}",
        "",
        "### Model Metrics",
        f"| Metric | Value | Threshold |",
        f"|--------|-------|-----------|",
        f"| avg_confidence | {metrics['avg_confidence']:.4f} | warn < {AVG_CONF_WARN} / crit < {AVG_CONF_CRIT} |",
        f"| coverage (conf ≥ 0.30) | {_fmt_pct(metrics['coverage_pct'])} ({metrics['facets_covered']}/{metrics['facets_total']}) | warn < {_fmt_pct(COVERAGE_WARN)} / crit < {_fmt_pct(COVERAGE_CRIT)} |",
        f"| bootstrap_loop_risk (7d) | {_fmt_pct(metrics['bootstrap_loop_risk'])} | warn > {_fmt_pct(LOOP_RISK_WARN)} / crit > {_fmt_pct(LOOP_RISK_CRIT)} |",
        "",
        "### Observation Sources (last 7 days)",
        f"- Total: {metrics['obs_7d_total']}",
        f"- AI-mediated (session_behavioral): {metrics['obs_7d_ai_mediated']} ({_fmt_pct(metrics['bootstrap_loop_risk'])})",
        f"- Independent: {metrics['obs_7d_independent']}",
        "",
    ]

    if neglected:
        lines += [
            f"### Neglected Facets (confidence < {NEGLECTED_CONF}, no independent obs in {NEGLECTED_DAYS}d)",
            "| Facet | Category | Confidence | Total obs | Recent independent |",
            "|-------|----------|------------|-----------|-------------------|",
        ]
        for f in neglected:
            lines.append(
                f"| {f['facet_id']} | {f['category']} | {f['confidence']:.3f} | "
                f"{f['observation_count']} | {f['recent_independent_obs']} |"
            )
        lines.append("")

    lines += [
        "### Recommended Actions",
        "- **If bootstrap_loop_risk > 75%**: prioritize non-agent evidence sources "
          "(checkins, Telegram, dump import) to rebuild independent observation base",
        "- **For neglected facets**: raise FGS weight or schedule targeted checkins "
          "focusing on the top 5 lowest-confidence facets",
        "- **If coverage falling**: review recency decay parameters "
          "(current half-life: 14 days) — consider extending for stable traits",
    ]

    return "\n".join(lines)


# ── Remediation actions ───────────────────────────────────────────────────────

HEALTH_OVERRIDES_FILE = RELIC_DIR / "health_overrides.json"
PAPERCLIP_WORKSPACE_ROOT = Path(
    os.environ.get(
        "PAPERCLIP_WORKSPACE_ROOT",
        str(Path.home() / ".paperclip" / "instances" / "default" / "workspaces"),
    )
)
MAX_QUESTIONS_DEGRADED = 4
MAX_QUESTIONS_CRITICAL = 5
PRIORITY_FACETS_N = 5


def apply_remediation(metrics: dict[str, Any], neglected: list[dict[str, Any]],
                       severity: str) -> None:
    """Write health_overrides.json so the question engine adapts immediately.

    - Raises daily question cap (3 → 4/5) to generate more independent observations
    - Flags top neglected facets for +0.20 FGS priority boost
    - Clears the file when the system is healthy
    """
    if severity == "healthy":
        if HEALTH_OVERRIDES_FILE.exists():
            from relic.relic_override_store import snapshot_before_write
            snapshot_before_write(HEALTH_OVERRIDES_FILE, "health", RELIC_DIR)
            HEALTH_OVERRIDES_FILE.unlink()
            info("remediation_cleared", reason="system_healthy")
        return

    max_q = MAX_QUESTIONS_CRITICAL if severity == "critical" else MAX_QUESTIONS_DEGRADED
    priority_facets = [f["facet_id"] for f in neglected[:PRIORITY_FACETS_N]]
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=13)).isoformat()

    overrides = {
        "severity": severity,
        "max_questions_per_day": max_q,
        "priority_facets": priority_facets,
        "loop_warning": metrics.get("bootstrap_loop_risk", 0.0) > LOOP_RISK_WARN,
        "expires_at": expires_at,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    from relic.relic_override_store import snapshot_before_write
    snapshot_before_write(HEALTH_OVERRIDES_FILE, "health", RELIC_DIR)
    HEALTH_OVERRIDES_FILE.write_text(json.dumps(overrides, indent=2))
    info("remediation_applied", severity=severity, max_questions_per_day=max_q,
         priority_facets=priority_facets, expires_at=expires_at)


# ── Paperclip submission ──────────────────────────────────────────────────────


def _export_to_workspace(metrics: dict, neglected: list[dict], debate: dict) -> None:
    """Esporta metriche, facets neglected e dibattito nel workspace del reviewer."""
    reviewer_id = os.environ.get("PAPERCLIP_HEALTH_REVIEWER_ID", "")
    export_debate(
        reviewer_id=reviewer_id,
        debate=debate,
        extra_files={"health_metrics": metrics, "neglected_facets": neglected},
    )


def submit_paperclip_issue(report: str, severity: str, metrics: dict[str, Any],
                           neglected: list[dict[str, Any]], debate: dict) -> None:
    api_url = os.environ.get("PAPERCLIP_API_URL", "http://localhost:3100")
    company_id = os.environ.get("PAPERCLIP_COMPANY_ID", "")
    api_key = os.environ.get("PAPERCLIP_HEALTH_ANALYST_KEY", "")
    reviewer_id = os.environ.get("PAPERCLIP_HEALTH_REVIEWER_ID", "")

    if not company_id or not api_key:
        info("paperclip_skip", reason="env vars not configured")
        return

    today = datetime.now(timezone.utc).date().isoformat()
    cov_str = f"{metrics.get('coverage_pct', 0) * 100:.1f}%"
    conf_str = f"{metrics.get('avg_confidence', 0):.3f}"
    loop_str = f"{metrics.get('bootstrap_loop_risk', 0) * 100:.1f}%"
    title = (
        f"[{today}] Health {severity.upper()} — "
        f"coverage={cov_str} conf={conf_str} loop_risk={loop_str}"
    )

    debate_md = (
        f"\n\n---\n## Internal Debate (Pro/Contra/Judge)\n\n"
        f"**Pro** ({debate.get('pro', {}).get('model', '?')}):\n"
        f"{debate.get('pro', {}).get('argument', '')}\n\n"
        f"**Contra** ({debate.get('contra', {}).get('model', '?')}):\n"
        f"{debate.get('contra', {}).get('argument', '')}\n\n"
        f"**Judge verdict**: {debate.get('judge', {}).get('verdict', '?')} "
        f"(confidence={debate.get('judge', {}).get('confidence', 0):.2f})\n"
        f"{debate.get('judge', {}).get('rationale', '')}"
    )
    full_description = report + debate_md
    payload: dict[str, Any] = {"title": title, "description": full_description}
    if reviewer_id:
        payload["assigneeAgentId"] = reviewer_id

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{api_url}/api/companies/{company_id}/issues",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            issue = json.loads(r.read())
            info("paperclip_issue_created", id=issue.get("id", "?")[:8],
                 severity=severity)
    except urllib.error.HTTPError as e:
        warn("paperclip_http_error", code=e.code, body=e.read().decode()[:200])
    except Exception as exc:
        warn("paperclip_error", error=str(exc))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    if not DB_PATH.exists():
        warn("db_not_found", path=str(DB_PATH))
        return 1

    db = _get_db()
    try:
        metrics = compute_metrics(db)
        if "error" in metrics:
            warn("metrics_error", **metrics)
            return 1

        neglected = find_neglected_facets(db)
        severity = score_severity(metrics)

        info("health_metrics", severity=severity, **metrics,
             neglected_count=len(neglected))

        report = format_report(metrics, neglected, severity)

        if severity == "healthy":
            info("health_ok", msg="all metrics within thresholds — no issue submitted")
            return 0

        debate = run_debate(
            domain="health",
            raw_data={"neglected_facets": neglected[:10]},
            metrics=metrics,
            report_text=report,
        )
        _export_to_workspace(metrics, neglected, debate)
        submit_paperclip_issue(report, severity, metrics, neglected, debate)
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
