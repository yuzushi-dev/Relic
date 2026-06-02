#!/usr/bin/env python3
"""Replay decision_events.jsonl through select_decision.

Reads canonical events (Plan §Task 1 schema), reconstructs the
``CheckinFeatures`` vector from each event's ``features_json`` (or a DB
lookup by ``features_id`` if ``--db`` is provided), re-runs
``select_decision``, and writes one JSONL line per source event with:

    {"event_id": ..., "old_event_kind": ..., "new_event_kind": ...,
     "old_posture": ..., "new_posture": ..., "changed": bool}

Output is byte-stable for identical input + policy version, which lets
CI assert behavior-preserving refactors.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, Iterable, Optional

from relic.checkin.policy import CheckinFeatures, EventType, Posture, select_decision


def _coerce_features(payload: dict) -> CheckinFeatures:
    valid = {f.name for f in fields(CheckinFeatures)}
    cleaned = {k: v for k, v in payload.items() if k in valid}
    return CheckinFeatures(**cleaned)


def _features_from_db(db_path: Path, features_id: int) -> Optional[dict]:
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    try:
        row = conn.execute(
            "SELECT features_json FROM checkin_features WHERE id = ?",
            (features_id,),
        ).fetchone()
        if not row or not row[0]:
            return None
        return json.loads(row[0])
    except (sqlite3.DatabaseError, json.JSONDecodeError):
        return None
    finally:
        conn.close()


def _iter_jsonl(path: Path) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def replay_event(
    event: dict,
    *,
    db_path: Optional[Path] = None,
    reflection_enabled: bool = False,
) -> dict:
    features_payload: Optional[dict] = event.get("features_json")
    if features_payload is None and db_path is not None:
        features_id = event.get("features_id")
        if isinstance(features_id, int):
            features_payload = _features_from_db(db_path, features_id)

    decision_type = event.get("decision_type") or "checkin"
    if features_payload is None:
        # Fall back to a zero vector: still deterministic.
        features = CheckinFeatures()
    elif isinstance(features_payload, str):
        try:
            features = _coerce_features(json.loads(features_payload))
        except json.JSONDecodeError:
            features = CheckinFeatures()
    else:
        features = _coerce_features(features_payload)

    decision = select_decision(
        features,
        decision_type=decision_type,
        policy_enabled=True,
        reflection_enabled=reflection_enabled,
    )
    old_event = event.get("event_kind")
    old_posture = event.get("posture")
    return {
        "event_id": event.get("event_id") or event.get("id"),
        "created_at": event.get("created_at"),
        "decision_type": decision_type,
        "old_event_kind": old_event,
        "new_event_kind": decision.event_type.value,
        "old_posture": old_posture,
        "new_posture": decision.posture.value,
        "reason": decision.reason,
        "changed": (old_event != decision.event_type.value) or (old_posture != decision.posture.value),
    }


def run_replay(
    *,
    input_path: Path,
    output_path: Path,
    db_path: Optional[Path] = None,
    reflection_enabled: bool = False,
) -> int:
    out_lines: list[str] = []
    count = 0
    for event in _iter_jsonl(input_path):
        record = replay_event(
            event,
            db_path=db_path,
            reflection_enabled=reflection_enabled,
        )
        out_lines.append(json.dumps(record, sort_keys=True))
        count += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
    return count


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Replay canonical decision events through select_decision")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Optional relic.db path to look up features_json by features_id when missing in JSONL.",
    )
    parser.add_argument(
        "--reflection-enabled",
        action="store_true",
        help="Enable reflective_mirror posture during replay (default: disabled).",
    )
    args = parser.parse_args(argv)
    count = run_replay(
        input_path=args.input,
        output_path=args.output,
        db_path=args.db,
        reflection_enabled=args.reflection_enabled,
    )
    print(json.dumps({"status": "ok", "replayed": count, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
