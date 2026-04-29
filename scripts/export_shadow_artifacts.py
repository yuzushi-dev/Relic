#!/usr/bin/env python3
"""Export comparable Relic artifacts from one RELIC_DATA_DIR."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _require(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {label} at {path}")


def _export_observations(conn: sqlite3.Connection, out_path: Path) -> None:
    rows = conn.execute(
        """
        SELECT facet_id, source_ref, extracted_signal, signal_strength, signal_position,
               source_type, context, context_metadata, created_at
        FROM observations
        ORDER BY facet_id, source_ref, id
        """
    ).fetchall()
    with out_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            payload = {
                "facet_id": row["facet_id"],
                "source_ref": row["source_ref"],
                "extracted_signal": row["extracted_signal"],
                "signal_strength": row["signal_strength"],
                "signal_position": row["signal_position"],
                "source_type": row["source_type"],
                "context": row["context"],
                "context_metadata": json.loads(row["context_metadata"]) if row["context_metadata"] else None,
                "created_at": row["created_at"],
            }
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _export_traits(conn: sqlite3.Connection, out_path: Path) -> None:
    rows = conn.execute(
        """
        SELECT facet_id, value_position, confidence, observation_count,
               last_observation_at, last_synthesis_at, notes, status
        FROM traits
        ORDER BY facet_id
        """
    ).fetchall()
    payload: dict[str, Any] = {}
    for row in rows:
        payload[row["facet_id"]] = {
            "score": row["value_position"],
            "confidence": row["confidence"],
            "evidence_count": row["observation_count"],
            "last_observation_at": row["last_observation_at"],
            "last_synthesis_at": row["last_synthesis_at"],
            "notes": row["notes"],
            "status": row["status"],
        }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def export_artifacts(data_dir: Path, out_dir: Path) -> None:
    db_path = data_dir / "relic.db"
    portrait_path = data_dir / "PORTRAIT.md"
    _require(db_path, "relic.db")
    _require(portrait_path, "PORTRAIT.md")

    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _export_observations(conn, out_dir / "observations.jsonl")
        _export_traits(conn, out_dir / "traits.json")
    finally:
        conn.close()
    shutil.copy2(portrait_path, out_dir / "PORTRAIT.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export observations, traits, and PORTRAIT.md from one Relic data dir.")
    parser.add_argument("--data-dir", required=True, help="Source RELIC_DATA_DIR")
    parser.add_argument("--out-dir", required=True, help="Destination artifact directory")
    args = parser.parse_args()

    try:
        export_artifacts(Path(args.data_dir), Path(args.out_dir))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"exported shadow artifacts from {args.data_dir} to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
