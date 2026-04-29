from __future__ import annotations

import sqlite3
from pathlib import Path

from datetime import datetime, timedelta, timezone

from mnemon import relic_healthcheck


def _init_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE observations (
            id INTEGER PRIMARY KEY,
            facet_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_ref TEXT,
            content TEXT NOT NULL,
            extracted_signal TEXT,
            signal_strength REAL DEFAULT 0.5,
            signal_position REAL,
            context TEXT,
            created_at TEXT NOT NULL,
            context_metadata TEXT,
            conversation_domain TEXT
        );
        CREATE TABLE hypotheses (
            id INTEGER PRIMARY KEY,
            hypothesis TEXT,
            status TEXT,
            confidence REAL,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )
    conn.close()


def test_check_agent_influence_counts_recent_rows_with_sqlite_datetime(tmp_path, monkeypatch):
    db_path = tmp_path / "relic.db"
    _init_db(db_path)

    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc)
    conn.executemany(
        """
        INSERT INTO observations (facet_id, source_type, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("f1", "session_behavioral", "ai row", (now - timedelta(days=2)).isoformat()),
            ("f2", "checkin_reply", "human row", (now - timedelta(days=3)).isoformat()),
            ("f3", "passive_chat", "chat row", (now - timedelta(days=4)).isoformat()),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(relic_healthcheck, "DB_PATH", db_path)

    result = relic_healthcheck.check_agent_influence()

    assert result["status"] == "ok"
    assert result["total"] == 3
    assert result["ai_mediated"] == 1
    assert result["agent_influence_index"] == 0.333
