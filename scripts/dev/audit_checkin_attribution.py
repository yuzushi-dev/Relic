#!/usr/bin/env python3
"""Read-only audit of historical check-in reply attribution.

Detects data-quality residue left by the pre-fix batch mis-attribution bug
(multiple checkin_exchanges asked in the same tick; a single subject reply was
captured against ORDER BY asked_at DESC LIMIT 1, possibly the wrong facet).

Two independent signals, NEITHER mutates the DB:

1. STRUCTURAL (deterministic): exchanges sharing an asked_at "batch" where one
   row got the reply and sibling rows were left un-replied (orphaned). These are
   the rows most likely to have stolen a reply meant for a sibling facet.

2. SEMANTIC (LLM re-judge): for every exchange that already has a reply, re-run
   extract_observation against its *recorded* facet. A substantive reply judged
   `informative=False` is a candidate mis-attribution (the reply does not speak
   to the facet it was filed under).

Usage:
    RELIC_HOME=~/.relic .venv/bin/python scripts/dev/audit_checkin_attribution.py
    ... --subject daniele          # restrict to one subject
    ... --no-llm                   # structural signal only (no Ollama calls)
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from relic.checkin.facet_updater import extract_observation
from relic.checkin.reply_capture import _is_substantive


def _subjects(relic_home: Path, only: str | None) -> list[str]:
    base = relic_home / "subjects"
    if not base.is_dir():
        return []
    out = []
    for p in sorted(base.iterdir()):
        if p.is_dir() and (p / "relic.db").exists():
            if only and p.name != only:
                continue
            out.append(p.name)
    return out


def _audit_subject(relic_home: Path, subject: str, use_llm: bool) -> dict:
    db = relic_home / "subjects" / subject / "relic.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # --- Signal 1: batches (asked within the same second, >1 exchange) ---
    # Group by second-precision prefix: the bug emitted siblings ~tens of ms
    # apart, so exact-timestamp grouping would miss them.
    batches = conn.execute(
        """SELECT substr(asked_at, 1, 19) AS bucket, COUNT(*) AS n,
                  SUM(CASE WHEN reply_text IS NOT NULL THEN 1 ELSE 0 END) AS replied
           FROM checkin_exchanges
           GROUP BY bucket HAVING n > 1 ORDER BY bucket"""
    ).fetchall()
    orphaned = []  # batches where 1 got reply, siblings stranded
    for b in batches:
        if b["replied"] >= 1 and b["replied"] < b["n"]:
            sibs = conn.execute(
                "SELECT id, facet_id, reply_text IS NOT NULL AS has_reply "
                "FROM checkin_exchanges WHERE substr(asked_at, 1, 19) = ? ORDER BY id",
                (b["bucket"],),
            ).fetchall()
            orphaned.append(
                {
                    "asked_at": b["bucket"],
                    "facets": [
                        f"{s['facet_id']}{'*' if s['has_reply'] else ''}" for s in sibs
                    ],
                }
            )

    # --- Signal 2: LLM re-judge of replied exchanges vs recorded facet ---
    replied = conn.execute(
        """SELECT ce.id, ce.facet_id, ce.question_text, ce.reply_text,
                  ce.observations_extracted,
                  f.name, f.description, f.spectrum_low, f.spectrum_high
           FROM checkin_exchanges ce JOIN facets f ON f.id = ce.facet_id
           WHERE ce.reply_text IS NOT NULL ORDER BY ce.asked_at"""
    ).fetchall()
    conn.close()

    rejudge = []
    if use_llm:
        for r in replied:
            substantive = _is_substantive(r["reply_text"])
            ext = extract_observation(
                exchange_id=r["id"],
                facet_id=r["facet_id"],
                facet_name=r["name"] or r["facet_id"],
                description=r["description"] or "",
                spectrum_low=r["spectrum_low"] or "low",
                spectrum_high=r["spectrum_high"] or "high",
                question_text=r["question_text"] or "",
                reply_text=r["reply_text"],
            )
            # Flag: substantive reply that does NOT inform its recorded facet,
            # and the LLM was actually reachable (no error).
            suspect = substantive and not ext.informative and ext.error is None
            rejudge.append(
                {
                    "id": r["id"],
                    "facet": r["facet_id"],
                    "extracted": bool(r["observations_extracted"]),
                    "substantive": substantive,
                    "informative_now": ext.informative,
                    "error": ext.error,
                    "suspect": suspect,
                    "reply_head": (r["reply_text"] or "")[:70].replace("\n", " "),
                }
            )

    return {
        "subject": subject,
        "n_replied": len(replied),
        "batches_total": len(batches),
        "orphaned_batches": orphaned,
        "rejudge": rejudge,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default=None)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    relic_home = Path(os.environ.get("RELIC_HOME") or Path.home() / ".relic")
    subjects = _subjects(relic_home, args.subject)
    if not subjects:
        print(f"No subjects with relic.db under {relic_home}/subjects")
        return 1

    use_llm = not args.no_llm
    for subj in subjects:
        rep = _audit_subject(relic_home, subj, use_llm)
        print(f"\n==== {rep['subject']} ====")
        print(f"replied exchanges: {rep['n_replied']} | batches(>1): {rep['batches_total']}")

        if rep["orphaned_batches"]:
            print(f"  STRUCTURAL — {len(rep['orphaned_batches'])} batch con sibling orfani "
                  f"(* = ha ricevuto la reply):")
            for o in rep["orphaned_batches"]:
                print(f"    {o['asked_at']}: {', '.join(o['facets'])}")
        else:
            print("  STRUCTURAL — nessun batch con sibling orfani")

        if use_llm:
            suspects = [x for x in rep["rejudge"] if x["suspect"]]
            errors = [x for x in rep["rejudge"] if x["error"]]
            print(f"  SEMANTIC — {len(suspects)}/{rep['n_replied']} reply sostanziose "
                  f"NON informative sul facet registrato (sospette):")
            for s in suspects:
                print(f"    ex {s['id']} [{s['facet']}] (extracted={s['extracted']}): "
                      f"\"{s['reply_head']}\"")
            if errors:
                print(f"  WARN — {len(errors)} re-giudizi falliti (LLM unreachable): "
                      f"ids {[e['id'] for e in errors]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
