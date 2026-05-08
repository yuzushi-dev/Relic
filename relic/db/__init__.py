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
    """Initialize the database with migrations."""
    from relic.paths import iter_migrations
    path = db_path or get_db_path()
    get_relic_home().mkdir(parents=True, exist_ok=True)
    conn = get_connection(path)
    try:
        for migration in iter_migrations():
            sql = migration.read_text()
            conn.executescript(sql)
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
