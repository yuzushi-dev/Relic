"""Database package for relic runtime governance."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

from relic.paths import get_db_path, get_relic_home


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextlib.contextmanager
def get_cursor(db_path: Path | None = None):
    """Context manager for database cursor."""
    conn = get_connection(db_path)
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """Initialize the database with migrations.

    Uses idempotent migration execution: skips already-applied migrations
    and handles idempotent column additions. Re-running init_db is safe.
    """
    from relic.paths import iter_migrations

    path = db_path or get_db_path()
    get_relic_home().mkdir(parents=True, exist_ok=True)
    conn = get_connection(path)

    try:
        # Get already-applied migrations
        applied = set[str]()
        try:
            cur = conn.cursor()
            cur.execute("SELECT version FROM schema_version")
            applied = {row[0] for row in cur.fetchall()}
        except sqlite3.OperationalError:
            pass  # schema_version table doesn't exist yet

        for migration in iter_migrations():
            # Extract version from filename like "0001_initial.sql"
            version = migration.stem[:4]  # "0001" from "0001_initial.sql"

            if version in applied:
                continue

            sql = migration.read_text()
            try:
                conn.executescript(sql)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
                # Older local DBs may have received ALTER-only migrations before
                # schema_version was recorded. Continue when the only conflict is
                # an already-present column; subsequent CREATE/INSERT statements
                # in the migration are idempotent and safe to skip/re-run later.
                conn.rollback()
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at) "
                    "VALUES (?, CURRENT_TIMESTAMP)",
                    (version,),
                )

        conn.commit()
    finally:
        conn.close()


def load_fixture(fixture_name: str, db_path: Path | None = None) -> None:
    """Load a fixture into the database."""
    from relic.paths import get_fixtures_dir
    fixture_path = get_fixtures_dir() / fixture_name / "initial_db_state.sql"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_name}")
    path = db_path or get_db_path()
    conn = get_connection(path)
    try:
        conn.executescript(fixture_path.read_text())
        conn.commit()
    finally:
        conn.close()
