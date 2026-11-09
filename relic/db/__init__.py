"""Database package for relic runtime governance."""

from __future__ import annotations

import contextlib
import fcntl
import logging
import re
import sqlite3
from pathlib import Path

from relic.paths import get_db_path, get_relic_home

logger = logging.getLogger(__name__)


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON")
    # Rollback-journal mode takes an exclusive lock and rewrites the journal file
    # on every commit, so concurrent subject writers serialise on fsync and the
    # stragglers time out. WAL lets readers run against a writer and makes the
    # many small commits cheap. Silently stays in the previous mode on
    # filesystems without shared memory (network mounts), which is why the
    # busy timeout above still has to be generous.
    conn.execute("PRAGMA journal_mode = WAL")
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


@contextlib.contextmanager
def _migration_lock(path: Path):
    """Serialise migration runs against the same database file.

    ``init_db`` reads ``schema_version`` into memory before applying anything, so
    concurrent first-time callers all see "nothing applied" and each replays the
    full migration set. Those replays are exclusive-lock DDL against one file, so
    the redundant runs queue up and the last ones exhaust SQLite's busy timeout
    with "database is locked". Holding the lock across both the read and the
    writes lets one caller migrate while the rest wait and then find the work
    already done.
    """
    lock_path = path.with_name(path.name + ".init.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def init_db(db_path: Path | None = None) -> None:
    """Initialize the database with migrations.

    Uses idempotent migration execution: skips already-applied migrations
    and handles idempotent column additions. Re-running init_db is safe.
    """
    from relic.paths import iter_migrations

    # Callers annotated for Path routinely pass str; the lock needs real Path ops.
    path = Path(db_path) if db_path else get_db_path()
    get_relic_home().mkdir(parents=True, exist_ok=True)

    with _migration_lock(path):
        _apply_migrations(path, iter_migrations())


_IDENT = r'"[^"]+"|`[^`]+`|\[[^\]]+\]|\w+'
_LEADING_NOISE_RE = re.compile(r"\A(?:\s+|--[^\n]*(?:\n|\Z)|/\*.*?\*/)*", re.DOTALL)
_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
_ADD_COLUMN_RE = re.compile(
    rf"ALTER\s+TABLE\s+(?:(?:{_IDENT})\s*\.\s*)?({_IDENT})\s+ADD\s+(?:COLUMN\s+)?({_IDENT})",
    re.IGNORECASE,
)


def _split_statements(sql: str) -> list[str]:
    """Split a migration script into single statements.

    Uses SQLite's own tokenizer (``complete_statement``) on each ``;`` candidate,
    so semicolons inside strings, quoted identifiers, comments and trigger bodies
    do not end a statement, and several statements on one line are still split.
    """
    statements: list[str] = []
    start = 0
    pos = 0
    while (idx := sql.find(";", pos)) != -1:
        if sqlite3.complete_statement(sql[start : idx + 1]):
            statements.append(sql[start : idx + 1])
            start = idx + 1
        pos = idx + 1
    tail = sql[start:]
    if _COMMENT_RE.sub("", tail).strip():
        statements.append(tail)
    return statements


def _unquote(ident: str) -> str:
    if len(ident) >= 2 and (ident[0], ident[-1]) in {('"', '"'), ("`", "`"), ("[", "]")}:
        return ident[1:-1]
    return ident


def _add_column_target(statement: str) -> tuple[str, str] | None:
    """Return ``(table, column)`` when the statement is ``ALTER TABLE .. ADD COLUMN``."""
    body = statement[_LEADING_NOISE_RE.match(statement).end() :]
    match = _ADD_COLUMN_RE.match(body)
    if match is None:
        return None
    return _unquote(match.group(1)), _unquote(match.group(2))


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND lower(name) = lower(?)",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pragma_table_info(?) WHERE lower(name) = lower(?)",
        (table, column),
    ).fetchone()
    return row is not None


def _has_missing_columns(conn: sqlite3.Connection, statements: list[str]) -> list[tuple[str, str]]:
    """Columns that a migration adds, whose table exists but which are absent."""
    missing = []
    for statement in statements:
        target = _add_column_target(statement)
        if target and _table_exists(conn, target[0]) and not _column_exists(conn, *target):
            missing.append(target)
    return missing


def _run_migration(conn: sqlite3.Connection, version: str, statements: list[str]) -> None:
    """Apply one migration file atomically.

    ``ALTER TABLE .. ADD COLUMN`` statements whose column already exists are
    skipped one by one, so a partially applied file is completed instead of being
    recorded as done. Everything runs in a single transaction and the version is
    recorded last: a failure rolls the whole file back and leaves it unrecorded.
    """
    assert not conn.in_transaction
    conn.isolation_level = None  # explicit BEGIN/COMMIT; executescript would auto-commit
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in statements:
            target = _add_column_target(statement)
            if target and _column_exists(conn, *target):
                continue
            conn.execute(statement)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) "
            "VALUES (?, CURRENT_TIMESTAMP)",
            (version,),
        )
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def _apply_migrations(path: Path, migrations) -> None:
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

        # Extract version from filename like "0001_initial.sql" -> "0001"
        parsed = {m.stem[:4]: _split_statements(m.read_text()) for m in migrations}

        # Databases hit by an earlier runner may record a version whose
        # ADD COLUMN statements never all ran. Re-run those files: the runner is
        # idempotent, so only the missing columns are added.
        # Invariant: migrations only ever add columns, never drop or rename them.
        for version, statements in parsed.items():
            if version not in applied:
                continue
            missing = _has_missing_columns(conn, statements)
            if missing:
                logger.warning(
                    "migration %s is recorded but columns are missing %s; re-applying",
                    version,
                    missing,
                )
                applied.discard(version)

        for version, statements in parsed.items():
            if version not in applied:
                _run_migration(conn, version, statements)
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
