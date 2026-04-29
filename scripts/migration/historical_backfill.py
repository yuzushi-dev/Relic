#!/usr/bin/env python3
"""Replay-safe historical observation backfill for canonical Relic slices."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_source_rows(source_db: Path, source_type: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT facet_id, source_type, source_ref, content, extracted_signal,
                   signal_strength, signal_position, context, context_metadata, created_at
            FROM observations
            WHERE source_type = ?
            ORDER BY created_at, id
            """,
            (source_type,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _derive_provenance(row: dict[str, Any], *, source_runtime: str, batch_id: str) -> dict[str, Any]:
    source_ref = str(row.get("source_ref") or "")
    source_session_id = None
    source_message_ref = source_ref or None
    if source_ref.startswith("session:"):
        parts = source_ref.split(":")
        if len(parts) >= 3:
            source_session_id = parts[1]
            source_message_ref = parts[2]
    elif ":" in source_ref:
        source_session_id, source_message_ref = source_ref.split(":", 1)
    return {
        "source_runtime": source_runtime,
        "source_session_id": source_session_id,
        "source_message_ref": source_message_ref,
        "source_timestamp": row.get("created_at"),
        "ingestion_mode": "backfill",
        "extractor_name": "historical_backfill",
        "extractor_version": "v1",
        "import_batch_id": batch_id,
    }


def _merge_context_metadata(row: dict[str, Any], *, provenance: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("context_metadata")
    metadata: dict[str, Any] = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                metadata = parsed
        except Exception:
            metadata = {"_raw_context_metadata": str(raw)}
    metadata["provenance"] = provenance
    return metadata


def _write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def _snapshot_target(conn: sqlite3.Connection) -> dict[str, Any]:
    total_observations = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    distinct_facets = conn.execute("SELECT COUNT(DISTINCT facet_id) FROM observations").fetchone()[0]
    return {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "total_observations": total_observations,
        "distinct_facets": distinct_facets,
    }


def run_backfill(
    *,
    source_db: Path,
    target_db: Path,
    source_type: str,
    out_dir: Path,
    batch_id: str,
    source_runtime: str,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = _read_source_rows(source_db, source_type)
    _write_jsonl(out_dir / "candidate_inputs.jsonl", candidates)

    manifest = {
        "batch_id": batch_id,
        "source_db": str(source_db),
        "target_db": str(target_db),
        "source_type": source_type,
        "source_runtime": source_runtime,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
    }

    target = sqlite3.connect(target_db)
    target.row_factory = sqlite3.Row
    imported_results: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    imported_count = 0
    duplicate_count = 0
    conflict_count = 0
    try:
        for row in candidates:
            existing = target.execute(
                """
                SELECT extracted_signal
                FROM observations
                WHERE facet_id = ? AND source_ref = ?
                """,
                (row["facet_id"], row["source_ref"]),
            ).fetchone()
            if existing:
                if (existing["extracted_signal"] or "") == (row.get("extracted_signal") or ""):
                    duplicate_count += 1
                    imported_results.append(
                        {
                            "status": "duplicate",
                            "facet_id": row["facet_id"],
                            "source_ref": row["source_ref"],
                        }
                    )
                    continue
                conflict_count += 1
                conflict = {
                    "status": "conflict",
                    "facet_id": row["facet_id"],
                    "source_ref": row["source_ref"],
                    "existing_extracted_signal": existing["extracted_signal"],
                    "incoming_extracted_signal": row.get("extracted_signal"),
                }
                conflicts.append(conflict)
                imported_results.append(conflict)
                continue

            provenance = _derive_provenance(row, source_runtime=source_runtime, batch_id=batch_id)
            context_metadata = _merge_context_metadata(row, provenance=provenance)
            created_at = str(row.get("created_at") or datetime.now(timezone.utc).isoformat())
            target.execute(
                """
                INSERT INTO observations (
                    facet_id, source_type, source_ref, content, extracted_signal,
                    signal_strength, signal_position, context, context_metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["facet_id"],
                    row["source_type"],
                    row["source_ref"],
                    row["content"],
                    row.get("extracted_signal"),
                    row.get("signal_strength", 0.5),
                    row.get("signal_position"),
                    row.get("context"),
                    json.dumps(context_metadata, ensure_ascii=False),
                    created_at,
                ),
            )
            target.execute(
                """
                UPDATE traits SET
                    observation_count = observation_count + 1,
                    last_observation_at = ?
                WHERE facet_id = ?
                """,
                (created_at, row["facet_id"]),
            )
            imported_count += 1
            imported_results.append(
                {
                    "status": "imported",
                    "facet_id": row["facet_id"],
                    "source_ref": row["source_ref"],
                }
            )

        target.commit()
        _write_jsonl(out_dir / "import_results.jsonl", imported_results)
        _write_jsonl(out_dir / "dedup_conflicts.jsonl", conflicts)
        snapshot = _snapshot_target(target)
        (out_dir / "post_import_snapshot.json").write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    finally:
        target.close()

    summary = {
        "batch_id": batch_id,
        "candidate_count": len(candidates),
        "imported_count": imported_count,
        "duplicate_count": duplicate_count,
        "conflict_count": conflict_count,
    }
    manifest.update(summary)
    (out_dir / "batch_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay-safe historical observation backfill for one source_type slice.")
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--source-type", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--source-runtime", default="openclaw")
    args = parser.parse_args()

    summary = run_backfill(
        source_db=Path(args.source_db),
        target_db=Path(args.target_db),
        source_type=args.source_type,
        out_dir=Path(args.out_dir),
        batch_id=args.batch_id,
        source_runtime=args.source_runtime,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
