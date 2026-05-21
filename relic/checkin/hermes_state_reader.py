"""Aggregate-only reader for Hermes ``state.db`` message metadata.

This module depends on Hermes' internal ``state.db`` / ``messages`` schema,
which is documented-internal and unstable. It is the single point in Relic's
check-in stack that knows how to read that table directly, so it can later be
swapped for Hermes' supported session-search API without changing callers.

Privacy invariant: helpers here return timestamps, numeric aggregates, and
boolean existence checks only. They never return raw message bodies.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class _MessagesSchema:
    time_column: str
    scope_column: str | None


def _state_db_path(hermes_home: Path) -> Path:
    return Path(hermes_home) / "state.db"


def _detect_time_column(columns: set[str]) -> str | None:
    if "timestamp" in columns:
        return "timestamp"
    if "created_at" in columns:
        return "created_at"
    return None


def _detect_scope_column(columns: set[str]) -> str | None:
    for candidate in ("session_id", "platform", "session"):
        if candidate in columns:
            return candidate
    return None


def _open_messages_db(hermes_home: Path) -> tuple[sqlite3.Connection, _MessagesSchema] | None:
    state_db = _state_db_path(hermes_home)
    conn: sqlite3.Connection | None = None
    try:
        if not state_db.exists():
            return None
        conn = sqlite3.connect(str(state_db), timeout=5.0)
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        time_column = _detect_time_column(columns)
        if time_column is None:
            conn.close()
            return None
        return conn, _MessagesSchema(
            time_column=time_column,
            scope_column=_detect_scope_column(columns),
        )
    except (OSError, sqlite3.Error):
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return None


def _close_quietly(conn: sqlite3.Connection) -> None:
    try:
        conn.close()
    except Exception:
        pass


def _scope_sql(schema: _MessagesSchema, session_or_platform: str | None) -> tuple[str, tuple[str, ...]]:
    if session_or_platform and schema.scope_column:
        return f" AND {schema.scope_column} = ?", (session_or_platform,)
    return "", ()


def _to_query_value(schema: _MessagesSchema, value: datetime) -> float | str:
    if schema.time_column == "timestamp":
        return value.timestamp()
    return value.isoformat()


def _parse_last_dt(schema: _MessagesSchema, raw_value: object) -> datetime | None:
    if raw_value is None:
        return None
    try:
        if schema.time_column == "timestamp":
            return datetime.fromtimestamp(float(raw_value), tz=timezone.utc)
        if isinstance(raw_value, str):
            return datetime.fromisoformat(raw_value)
    except (OSError, OverflowError, TypeError, ValueError):
        return None
    return None


def last_subject_msg_at(
    hermes_home: Path,
    *,
    session_or_platform: str | None = None,
) -> Optional[datetime]:
    """Return the latest user-authored Hermes message timestamp, if readable."""
    opened = _open_messages_db(hermes_home)
    if opened is None:
        return None
    conn, schema = opened
    try:
        scope_sql, scope_params = _scope_sql(schema, session_or_platform)
        row = conn.execute(
            f"SELECT MAX({schema.time_column}) FROM messages WHERE role = 'user'{scope_sql}",
            scope_params,
        ).fetchone()
        return _parse_last_dt(schema, row[0] if row else None)
    except (OSError, sqlite3.Error):
        return None
    finally:
        _close_quietly(conn)


def subject_avg_tokens(
    hermes_home: Path,
    since: datetime,
    *,
    session_or_platform: str | None = None,
) -> Optional[float]:
    """Return ``AVG(LENGTH(content) / 4.0)`` for user messages since ``since``."""
    opened = _open_messages_db(hermes_home)
    if opened is None:
        return None
    conn, schema = opened
    try:
        scope_sql, scope_params = _scope_sql(schema, session_or_platform)
        row = conn.execute(
            "SELECT AVG(LENGTH(content) / 4.0) FROM messages "
            f"WHERE role = 'user' AND {schema.time_column} >= ?{scope_sql}",
            (_to_query_value(schema, since), *scope_params),
        ).fetchone()
        if not row or row[0] is None:
            return None
        return float(row[0])
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return None
    finally:
        _close_quietly(conn)


def has_user_reply_between(
    hermes_home: Path,
    start: datetime,
    end: datetime,
    *,
    session_or_platform: str | None = None,
) -> bool:
    """Return whether a user-authored Hermes message exists in ``[start, end]``."""
    opened = _open_messages_db(hermes_home)
    if opened is None:
        return False
    conn, schema = opened
    try:
        scope_sql, scope_params = _scope_sql(schema, session_or_platform)
        row = conn.execute(
            "SELECT 1 FROM messages "
            f"WHERE role = 'user' AND {schema.time_column} >= ? AND {schema.time_column} <= ?"
            f"{scope_sql} LIMIT 1",
            (_to_query_value(schema, start), _to_query_value(schema, end), *scope_params),
        ).fetchone()
        return row is not None
    except (OSError, sqlite3.Error):
        return False
    finally:
        _close_quietly(conn)
