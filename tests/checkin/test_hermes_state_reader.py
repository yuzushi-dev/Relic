from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relic.checkin.hermes_state_reader import (
    has_user_reply_between,
    last_subject_msg_at,
    subject_avg_tokens,
)


def _init_messages_db(
    hermes_home: Path,
    *,
    schema: str,
    rows: list[dict],
    include_session_id: bool = False,
    include_platform: bool = False,
) -> Path:
    hermes_home.mkdir(parents=True, exist_ok=True)
    state_db = hermes_home / "state.db"
    conn = sqlite3.connect(str(state_db))
    try:
        if schema == "timestamp":
            columns = [
                "id INTEGER PRIMARY KEY",
                "role TEXT",
                "content TEXT",
                "timestamp REAL",
            ]
            if include_session_id:
                columns.insert(1, "session_id TEXT")
            if include_platform:
                columns.insert(1, "platform TEXT")
            conn.execute(f"CREATE TABLE messages ({', '.join(columns)})")
            for row in rows:
                cols = []
                vals = []
                if include_session_id:
                    cols.append("session_id")
                    vals.append(row.get("session_id"))
                if include_platform:
                    cols.append("platform")
                    vals.append(row.get("platform"))
                cols.extend(["role", "content", "timestamp"])
                vals.extend([row["role"], row["content"], row["timestamp"]])
                conn.execute(
                    f"INSERT INTO messages ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                    vals,
                )
        elif schema == "created_at":
            columns = [
                "id INTEGER PRIMARY KEY",
                "role TEXT",
                "content TEXT",
                "created_at TEXT",
            ]
            if include_session_id:
                columns.insert(1, "session_id TEXT")
            if include_platform:
                columns.insert(1, "platform TEXT")
            conn.execute(f"CREATE TABLE messages ({', '.join(columns)})")
            for row in rows:
                cols = []
                vals = []
                if include_session_id:
                    cols.append("session_id")
                    vals.append(row.get("session_id"))
                if include_platform:
                    cols.append("platform")
                    vals.append(row.get("platform"))
                cols.extend(["role", "content", "created_at"])
                vals.extend([row["role"], row["content"], row["created_at"]])
                conn.execute(
                    f"INSERT INTO messages ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                    vals,
                )
        else:
            raise ValueError(f"unknown schema: {schema}")
        conn.commit()
    finally:
        conn.close()
    return state_db


@pytest.mark.parametrize("schema", ["timestamp", "created_at"])
def test_last_subject_msg_at_and_avg_tokens_support_both_schemas(tmp_path: Path, schema: str):
    hermes_home = tmp_path / schema
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    recent = now - timedelta(hours=3)
    older = now - timedelta(days=20)

    if schema == "timestamp":
        rows = [
            {"role": "user", "content": "1234", "timestamp": older.timestamp()},
            {"role": "assistant", "content": "ignore-me", "timestamp": now.timestamp()},
            {"role": "user", "content": "12345678", "timestamp": recent.timestamp()},
        ]
    else:
        rows = [
            {"role": "user", "content": "1234", "created_at": older.isoformat()},
            {"role": "assistant", "content": "ignore-me", "created_at": now.isoformat()},
            {"role": "user", "content": "12345678", "created_at": recent.isoformat()},
        ]

    _init_messages_db(hermes_home, schema=schema, rows=rows)

    assert last_subject_msg_at(hermes_home) == recent
    assert subject_avg_tokens(hermes_home, now - timedelta(days=14)) == pytest.approx(2.0)


@pytest.mark.parametrize("schema", ["timestamp", "created_at"])
def test_has_user_reply_between_supports_both_schemas(tmp_path: Path, schema: str):
    hermes_home = tmp_path / schema
    start = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=24)
    inside = start + timedelta(hours=2)
    outside = end + timedelta(minutes=1)

    if schema == "timestamp":
        rows = [
            {"role": "assistant", "content": "ignore", "timestamp": inside.timestamp()},
            {"role": "user", "content": "late", "timestamp": outside.timestamp()},
            {"role": "user", "content": "reply", "timestamp": inside.timestamp()},
        ]
    else:
        rows = [
            {"role": "assistant", "content": "ignore", "created_at": inside.isoformat()},
            {"role": "user", "content": "late", "created_at": outside.isoformat()},
            {"role": "user", "content": "reply", "created_at": inside.isoformat()},
        ]

    _init_messages_db(hermes_home, schema=schema, rows=rows)

    assert has_user_reply_between(hermes_home, start, end) is True
    assert has_user_reply_between(hermes_home, start - timedelta(days=3), start - timedelta(days=2)) is False


def test_helpers_fail_open_when_state_db_missing(tmp_path: Path):
    hermes_home = tmp_path / "missing"
    start = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=24)

    assert last_subject_msg_at(hermes_home) is None
    assert subject_avg_tokens(hermes_home, start) is None
    assert has_user_reply_between(hermes_home, start, end) is False


def test_optional_session_scope_filters_when_column_exists(tmp_path: Path):
    hermes_home = tmp_path / "session-scope"
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "session_id": "s1",
            "role": "user",
            "content": "1234",
            "timestamp": (now - timedelta(hours=2)).timestamp(),
        },
        {
            "session_id": "s2",
            "role": "user",
            "content": "12345678",
            "timestamp": (now - timedelta(hours=1)).timestamp(),
        },
    ]
    _init_messages_db(hermes_home, schema="timestamp", rows=rows, include_session_id=True)

    assert last_subject_msg_at(hermes_home, session_or_platform="s1") == now - timedelta(hours=2)
    assert subject_avg_tokens(
        hermes_home,
        now - timedelta(days=14),
        session_or_platform="s1",
    ) == pytest.approx(1.0)
    assert has_user_reply_between(
        hermes_home,
        now - timedelta(hours=3),
        now,
        session_or_platform="s1",
    ) is True
