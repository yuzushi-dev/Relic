"""Tests for the per-subject schema bootstrap (relic.checkin.db_init).

Contract:
- init_db stamps SCHEMA_VERSION into the schema_version table (auditable
  per-subject schema, independent of the global migration numbering).
- The vestigial `inbox` table (never read/written by runtime code) is no longer
  created.
- init_db is idempotent: re-running keeps a single schema_version row.
- seed_facets seeds exactly the 60 canonical facets with NULL-value traits.
"""
from __future__ import annotations

from pathlib import Path

from relic.checkin.db_init import SCHEMA_VERSION, init_db, seed_facets


def _tables(conn) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def test_schema_version_stamped(tmp_path: Path):
    conn = init_db(tmp_path / "relic.db")
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    conn.close()
    assert rows == [(SCHEMA_VERSION,)]


def test_inbox_table_not_created(tmp_path: Path):
    conn = init_db(tmp_path / "relic.db")
    tables = _tables(conn)
    conn.close()
    assert "inbox" not in tables
    # Core tables still present.
    assert {"facets", "traits", "observations", "checkin_exchanges"} <= tables


def test_init_db_idempotent(tmp_path: Path):
    db_path = tmp_path / "relic.db"
    init_db(db_path).close()
    conn = init_db(db_path)  # second run must not duplicate the version row
    count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    conn.close()
    assert count == 1


def test_seed_facets_count_and_null_traits(tmp_path: Path):
    conn = init_db(tmp_path / "relic.db")
    inserted = seed_facets(conn)
    n_facets = conn.execute("SELECT COUNT(*) FROM facets").fetchone()[0]
    n_traits = conn.execute("SELECT COUNT(*) FROM traits").fetchone()[0]
    n_null = conn.execute(
        "SELECT COUNT(*) FROM traits WHERE value_position IS NULL"
    ).fetchone()[0]
    conn.close()
    assert inserted == 60
    assert n_facets == 60
    assert n_traits == 60
    assert n_null == 60  # traits seed with NULL value_position by design
