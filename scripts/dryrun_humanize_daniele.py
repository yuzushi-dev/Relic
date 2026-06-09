#!/usr/bin/env python3
"""Dry-run harness for the humanize-interaction branch, subject daniele only.

Copies daniele's relic subject data into a throwaway RELIC_HOME and points
HERMES_HOME at an empty throwaway dir, then exercises the three decision lanes
and prints the gate messages + deliver context. Nothing is dispatched: the
checkin_media_dispatcher is never invoked and the real homes are never touched.

Usage:
    python3 scripts/dryrun_humanize_daniele.py [--subject daniele] [--days N]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="daniele")
    parser.add_argument("--days", type=int, default=14,
                        help="days to simulate for cadence/hook statistics")
    args = parser.parse_args()
    subject = args.subject
    if subject != "daniele":
        print("ERROR: only subject 'daniele' is authorized for testing", file=sys.stderr)
        return 1

    real_subject_home = Path.home() / ".relic" / "subjects" / subject
    if not real_subject_home.exists():
        print(f"ERROR: {real_subject_home} not found", file=sys.stderr)
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="relic-dryrun-"))
    relic_home = tmp / "relic"
    hermes_home = tmp / "hermes"
    (relic_home / "subjects").mkdir(parents=True)
    hermes_home.mkdir(parents=True)
    shutil.copytree(real_subject_home, relic_home / "subjects" / subject)
    print(f"[dryrun] sandbox: {tmp}")

    os.environ["RELIC_HOME"] = str(relic_home)
    os.environ["HERMES_HOME"] = str(hermes_home)
    os.environ["RELIC_NATURAL_CADENCE"] = "1"
    # Force-mode bypasses delivery windows so the dry run is time-independent.
    from relic.gumi_plugin.cron_wiring import (
        _diegetic_hook_today,
        _natural_cadence_skip_today,
        _window_jitter_minute,
        make_decision,
    )
    from relic.checkin.context_builder import build_deliver_context
    from relic.checkin.question_engine import select_followup
    import sqlite3

    print("\n=== gate output per lane (force, sandboxed) ===")
    for dtype in ("checkin", "diegetic", "proactivity"):
        decision, reasons, data = make_decision(
            subject_id=subject,
            gumi_instance_id=f"gumi-{subject}",
            hermes_profile_id=subject,
            force=True,
            decision_type=dtype,
        )
        print(f"\n--- {dtype} ---")
        print(f"decision: {decision.value}  reasons: {[r.value for r in reasons]}")
        if data:
            print(data["message"])

    print("\n=== deliver context (checkin/ask, no persist) ===")
    ctx = build_deliver_context(
        subject,
        hermes_home,
        relic_home,
        event_type="checkin",
        posture="ask",
        persist_topic_hint=False,
    )
    print(ctx or "(empty)")

    print("\n=== follow-up candidate (live data, read-only) ===")
    db = relic_home / "subjects" / subject / "relic.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cand = select_followup(conn)
    finally:
        conn.close()
    print(json.dumps(cand, ensure_ascii=False, indent=2) if cand else "(none)")

    print(f"\n=== cadence simulation, next {args.days} days ===")
    today = datetime.now(timezone.utc)
    window = (9, 0, 11, 0)
    for i in range(args.days):
        day = today + timedelta(days=i)
        skip_d = _natural_cadence_skip_today(subject, "diegetic", day)
        skip_p = _natural_cadence_skip_today(subject, "proactivity", day)
        hook = _diegetic_hook_today(subject, day)
        jit = _window_jitter_minute(subject, window, day)
        print(
            f"{day.date()}  diegetic={'skip' if skip_d else ('hook' if hook else 'send')}"
            f"  proactive={'skip' if skip_p else 'send'}"
            f"  window-fire={jit // 60:02d}:{jit % 60:02d}"
        )

    print(f"\n[dryrun] sandbox kept at {tmp} for inspection (delete manually)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
