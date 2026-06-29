"""Per-subject watermark for idempotent passive observation extraction.

Tracks the last ``state.db`` message timestamp consumed per subject in the
per-subject ``relic.db`` (table ``passive_extraction_state``). The setter is
monotonic: the watermark never moves backward.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def get_watermark(conn: sqlite3.Connection, subject_id: str) -> float:
    row = conn.execute(
        "SELECT last_processed_ts FROM passive_extraction_state WHERE subject_id=?",
        (subject_id,),
    ).fetchone()
    return float(row[0]) if row else 0.0


def set_watermark(conn: sqlite3.Connection, subject_id: str, ts: float) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO passive_extraction_state (subject_id, last_processed_ts, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(subject_id) DO UPDATE SET
               last_processed_ts = MAX(passive_extraction_state.last_processed_ts, excluded.last_processed_ts),
               updated_at = excluded.updated_at""",
        (subject_id, float(ts), now),
    )
    conn.commit()
