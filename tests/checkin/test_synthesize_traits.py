"""Tests for facet_updater.synthesize_traits (batch trait re-synthesis).

Contract:
- a facet with abundant consistent evidence but low stored confidence is raised
  toward the governance cap (MULTI_EVIDENCE_CAP = 0.55), never above it;
- monotonic: a facet already above the evidence-justified confidence is left
  untouched (no lowering of reviewed/bulk values);
- corrected facets are skipped;
- value_position is the strength-weighted mean of observations.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from relic.checkin.db_init import init_db, seed_facets
from relic.checkin.facet_updater import synthesize_traits
from relic.profile.inferred_fields import MULTI_EVIDENCE_CAP


@pytest.fixture()
def conn(tmp_path):
    c = init_db(tmp_path / "relic.db")
    seed_facets(c)
    yield c
    c.close()


def _facet_id(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT id FROM facets LIMIT 1").fetchone()[0]


def _add_obs(conn, facet_id, position, strength=0.7, n=1):
    now = datetime.now(timezone.utc).isoformat()
    for i in range(n):
        conn.execute(
            """INSERT INTO observations
               (facet_id, source_type, source_ref, content, extracted_signal,
                signal_strength, signal_position, created_at)
               VALUES (?, 'passive_chat', ?, '', '{}', ?, ?, ?)""",
            (facet_id, f"t{i}", strength, position, now),
        )
    conn.commit()


def test_abundant_consistent_evidence_raises_confidence(conn):
    f = _facet_id(conn)
    conn.execute(
        "INSERT OR REPLACE INTO traits (facet_id, value_position, confidence, observation_count, status) "
        "VALUES (?, 0.5, 0.20, 80, 'active')",
        (f,),
    )
    conn.commit()
    _add_obs(conn, f, position=0.8, n=80)

    changes = synthesize_traits(conn)
    assert any(c["facet_id"] == f for c in changes)

    conf, pos = conn.execute(
        "SELECT confidence, value_position FROM traits WHERE facet_id=?", (f,)
    ).fetchone()
    assert conf > 0.20                      # raised
    assert conf <= MULTI_EVIDENCE_CAP       # never above governance cap
    assert abs(pos - 0.8) < 1e-6            # weighted mean of the evidence


def test_monotonic_does_not_lower_existing_confidence(conn):
    f = _facet_id(conn)
    conn.execute(
        "INSERT OR REPLACE INTO traits (facet_id, value_position, confidence, observation_count, status) "
        "VALUES (?, 0.3, 0.77, 700, 'active')",
        (f,),
    )
    conn.commit()
    _add_obs(conn, f, position=0.8, n=5)  # evidence justifies <= cap (0.55) < 0.77

    synthesize_traits(conn)
    conf, pos = conn.execute(
        "SELECT confidence, value_position FROM traits WHERE facet_id=?", (f,)
    ).fetchone()
    assert conf == 0.77        # untouched
    assert pos == 0.3          # value_position untouched too


def test_corrected_facet_is_skipped(conn):
    f = _facet_id(conn)
    conn.execute(
        "INSERT OR REPLACE INTO traits (facet_id, value_position, confidence, observation_count, status) "
        "VALUES (?, 0.5, 0.10, 5, 'corrected')",
        (f,),
    )
    conn.commit()
    _add_obs(conn, f, position=0.9, n=40)

    changes = synthesize_traits(conn)
    assert all(c["facet_id"] != f for c in changes)
    conf = conn.execute("SELECT confidence FROM traits WHERE facet_id=?", (f,)).fetchone()[0]
    assert conf == 0.10


def test_dry_run_writes_nothing(conn):
    f = _facet_id(conn)
    conn.execute(
        "INSERT OR REPLACE INTO traits (facet_id, value_position, confidence, observation_count, status) "
        "VALUES (?, 0.5, 0.20, 80, 'active')",
        (f,),
    )
    conn.commit()
    _add_obs(conn, f, position=0.8, n=80)

    changes = synthesize_traits(conn, dry_run=True)
    assert changes  # preview is populated
    conf = conn.execute("SELECT confidence FROM traits WHERE facet_id=?", (f,)).fetchone()[0]
    assert conf == 0.20  # unchanged on disk
