"""Regression tests for the SQLite migration runner (issue #5).

A migration file with several ``ALTER TABLE .. ADD COLUMN`` statements used to be
recorded as fully applied as soon as one column already existed, silently
skipping the remaining statements.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from pathlib import Path

import pytest

from relic.db import (
    _add_column_target,
    _apply_migrations,
    _run_migration,
    _split_statements,
    init_db,
)
from relic.paths import get_migrations_dir


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_HOME", str(tmp_path / "home"))


def _files() -> list[Path]:
    return sorted(get_migrations_dir().glob("[0-9]*.sql"))


def _columns(path: Path, table: str) -> list[str]:
    with sqlite3.connect(path) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _versions(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT version FROM schema_version")}


def _schema(path: Path) -> list[tuple]:
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()


def _legacy_apply(path: Path, files: list[Path]) -> None:
    """The pre-fix runner (executescript per file), used as a schema oracle."""
    conn = sqlite3.connect(path)
    try:
        for f in files:
            conn.executescript(f.read_text())
        conn.commit()
    finally:
        conn.close()


# --- splitter / ALTER recognition -------------------------------------------


def test_split_handles_semicolons_in_strings_and_comments():
    sql = (
        "-- leading; comment\n"
        "INSERT INTO t VALUES ('a;b');\n"
        "/* block; comment */ CREATE TABLE x (c TEXT DEFAULT ';');\n"
    )
    parts = _split_statements(sql)
    assert len(parts) == 2
    assert "'a;b'" in parts[0]
    assert "CREATE TABLE x" in parts[1]


def test_split_two_statements_on_one_line_and_no_trailing_semicolon():
    parts = _split_statements("SELECT 1; SELECT 2;\nSELECT 3")
    assert [p.strip() for p in parts] == ["SELECT 1;", "SELECT 2;", "SELECT 3"]


def test_split_discards_trailing_comments_only():
    assert len(_split_statements("SELECT 1;\n-- done\n/* bye */\n")) == 1


def test_split_keeps_trigger_body_whole():
    sql = "CREATE TRIGGER tr AFTER INSERT ON t BEGIN UPDATE t SET a = 1; END;\nSELECT 1;"
    parts = _split_statements(sql)
    assert len(parts) == 2
    assert parts[0].strip().endswith("END;")


@pytest.mark.parametrize(
    "stmt",
    [
        "ALTER TABLE t ADD COLUMN c TEXT;",
        "alter table t add c text;",
        'ALTER TABLE "t" ADD COLUMN "c" TEXT;',
        "ALTER TABLE `t` ADD COLUMN `c` TEXT;",
        "ALTER TABLE [t] ADD COLUMN [c] TEXT;",
        "ALTER TABLE main.t ADD COLUMN c TEXT;",
        "-- note\n  /* x */ ALTER TABLE t ADD COLUMN c TEXT;",
    ],
)
def test_add_column_target_variants(stmt):
    assert _add_column_target(stmt) == ("t", "c")


@pytest.mark.parametrize(
    "stmt",
    [
        "ALTER TABLE t RENAME TO u;",
        "ALTER TABLE t RENAME COLUMN a TO b;",
        "CREATE TABLE t (c TEXT);",
        "INSERT INTO t VALUES ('ALTER TABLE t ADD COLUMN c');",
    ],
)
def test_add_column_target_ignores_other_statements(stmt):
    assert _add_column_target(stmt) is None


# --- the bug from issue #5 --------------------------------------------------


def test_partial_alter_is_completed(tmp_path):
    db = tmp_path / "partial.db"
    files = _files()
    _apply_migrations(db, files[:8])
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE checkin_exchanges ADD COLUMN posture TEXT")

    _apply_migrations(db, [files[8]])  # 0009_checkin_naturalness.sql

    cols = _columns(db, "checkin_exchanges")
    assert "posture" in cols and "response_latency_seconds" in cols
    assert "0009" in _versions(db)


def test_database_damaged_by_old_runner_is_repaired(tmp_path, caplog):
    db = tmp_path / "damaged.db"
    files = _files()
    _apply_migrations(db, files[:9])
    # Recreate the old failure: 0009 recorded, second column missing.
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE checkin_exchanges DROP COLUMN response_latency_seconds")
    assert "response_latency_seconds" not in _columns(db, "checkin_exchanges")
    assert "0009" in _versions(db)

    with caplog.at_level(logging.WARNING, logger="relic.db"):
        _apply_migrations(db, files)

    assert "response_latency_seconds" in _columns(db, "checkin_exchanges")
    assert "0009" in _versions(db)
    assert any("0009" in r.getMessage() for r in caplog.records)


def test_rerun_is_idempotent(tmp_path):
    db = tmp_path / "idem.db"
    files = _files()
    _apply_migrations(db, files)
    before = (_schema(db), _versions(db))
    _apply_migrations(db, files)
    _apply_migrations(db, files)
    assert (_schema(db), _versions(db)) == before


def test_failure_rolls_back_whole_file(tmp_path):
    db = tmp_path / "atomic.db"
    m1 = tmp_path / "0001_base.sql"
    m1.write_text(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version TEXT PRIMARY KEY, applied_at TEXT);\n"
        "CREATE TABLE t (a TEXT);\n"
    )
    m2 = tmp_path / "0002_bad.sql"
    m2.write_text(
        "ALTER TABLE t ADD COLUMN b TEXT;\n"
        "ALTER TABLE t ADD COLUMN c TEXT;\n"
        "THIS IS NOT SQL;\n"
    )
    with pytest.raises(sqlite3.OperationalError):
        _apply_migrations(db, [m1, m2])

    assert _columns(db, "t") == ["a"]  # b and c rolled back
    assert _versions(db) == {"0001"}  # 0002 not recorded

    m2.write_text("ALTER TABLE t ADD COLUMN b TEXT;\nALTER TABLE t ADD COLUMN c TEXT;\n")
    _apply_migrations(db, [m1, m2])
    assert _columns(db, "t") == ["a", "b", "c"]
    assert _versions(db) == {"0001", "0002"}


def test_failed_migration_leaves_connection_out_of_transaction(tmp_path):
    from relic.db import get_connection

    conn = get_connection(tmp_path / "txn.db")
    try:
        conn.execute("CREATE TABLE schema_version (version TEXT PRIMARY KEY, applied_at TEXT)")
        conn.execute("CREATE TABLE t (a TEXT)")
        stmts = _split_statements("ALTER TABLE t ADD COLUMN b TEXT; NOT SQL;")
        with pytest.raises(sqlite3.OperationalError):
            _run_migration(conn, "0001", stmts)
        assert not conn.in_transaction
        assert [r[1] for r in conn.execute("PRAGMA table_info(t)")] == ["a"]
    finally:
        conn.close()


def test_non_duplicate_errors_still_propagate(tmp_path):
    db = tmp_path / "err.db"
    m1 = tmp_path / "0001_base.sql"
    m1.write_text(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version TEXT PRIMARY KEY, applied_at TEXT);\n"
        "ALTER TABLE missing_table ADD COLUMN x TEXT;\n"
    )
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        _apply_migrations(db, [m1])
    assert not db.exists() or "schema_version" not in {r[1] for r in _schema(db)}


# --- no regression for normal paths ------------------------------------------


def test_fresh_database_matches_legacy_runner(tmp_path):
    new, old = tmp_path / "new.db", tmp_path / "old.db"
    _apply_migrations(new, _files())
    _legacy_apply(old, _files())
    assert _schema(new) == _schema(old)
    assert _versions(new) == _versions(old) == {f.stem[:4] for f in _files()}


def test_upgrade_from_0008_reaches_latest(tmp_path):
    db = tmp_path / "upgrade.db"
    files = _files()
    _apply_migrations(db, files[:8])
    _apply_migrations(db, files)
    assert _versions(db) == {f.stem[:4] for f in files}
    ref = tmp_path / "ref.db"
    _apply_migrations(ref, files)
    assert _schema(db) == _schema(ref)


def test_concurrent_init_db_is_safe(tmp_path):
    db = tmp_path / "conc.db"
    errors: list[BaseException] = []

    def run() -> None:
        try:
            init_db(db)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert _versions(db) == {f.stem[:4] for f in _files()}


# --- review follow-ups -------------------------------------------------------


def test_repair_keeps_original_applied_at(tmp_path):
    db = tmp_path / "ts.db"
    files = _files()
    _apply_migrations(db, files)
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE checkin_exchanges DROP COLUMN response_latency_seconds")
        conn.execute("UPDATE schema_version SET applied_at = '2020-01-01 00:00:00'")

    _apply_migrations(db, files)

    with sqlite3.connect(db) as conn:
        rows = dict(conn.execute("SELECT version, applied_at FROM schema_version"))
    assert rows["0009"] == "2020-01-01 00:00:00"
    assert "response_latency_seconds" in _columns(db, "checkin_exchanges")


def test_registered_version_with_absent_table_is_not_rerun(tmp_path):
    """The repair only looks at tables that exist: no spurious 'no such table'."""
    db = tmp_path / "absent.db"
    m1 = tmp_path / "0001_base.sql"
    m1.write_text(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version TEXT PRIMARY KEY, applied_at TEXT);\n"
        "ALTER TABLE ghost ADD COLUMN x TEXT;\n"
    )
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE schema_version (version TEXT PRIMARY KEY, applied_at TEXT)")
        conn.execute("INSERT INTO schema_version VALUES ('0001', 'then')")

    _apply_migrations(db, [m1])  # would raise 'no such table: ghost' if re-run

    assert _versions(db) == {"0001"}


def test_migration_files_keep_the_repair_invariants():
    """The repair re-runs whole files, which is only safe while they stay idempotent."""
    for f in _files():
        body = "\n".join(
            line for line in f.read_text().splitlines() if not line.lstrip().startswith("--")
        )
        assert not re.search(r"\b(DROP|RENAME)\b", body, re.IGNORECASE), f.name
        for stmt in _split_statements(body):
            if re.match(r"\s*CREATE\s+(TABLE|INDEX|UNIQUE\s+INDEX|VIEW)\b", stmt, re.IGNORECASE):
                assert re.search(r"IF\s+NOT\s+EXISTS", stmt, re.IGNORECASE), (f.name, stmt[:60])
            if re.match(r"\s*(INSERT|UPDATE|DELETE)\b", stmt, re.IGNORECASE):
                assert re.match(r"\s*INSERT\s+OR\s+(REPLACE|IGNORE)\b", stmt, re.IGNORECASE), (
                    f.name,
                    stmt[:60],
                )
