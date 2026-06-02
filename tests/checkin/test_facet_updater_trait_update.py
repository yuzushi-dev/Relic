"""Regression tests for trait value_position updates in facet_updater.

Contract:
- A facet's first observation must ADOPT the extracted signal_position even
  though seed_facets() pre-creates the trait row with value_position = NULL.
  Regression: the ON CONFLICT blend computed 0.7*NULL + 0.3*signal = NULL,
  silently discarding the first observation's value (observed on subject
  "barbara": informative reply, observation written, trait value_position NULL).
- A subsequent observation blends 70% prior / 30% new signal.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from relic.checkin.db_init import init_db, seed_facets
from relic.checkin.facet_updater import process_pending_exchanges

_FACET = "cognitive.abstraction_level"


def _stub_llm(signal_position: float):
    """Return an llm_client callable yielding an informative extraction."""

    def _client(_system: str, _prompt: str) -> dict:
        return {
            "informative": True,
            "signal_position": signal_position,
            "signal_strength": 0.7,
            "observation_summary": "osservazione di prova non clinica",
            "confidence_delta": 0.15,
        }

    return _client


def _seed_exchange(conn: sqlite3.Connection, reply: str) -> None:
    conn.execute(
        "INSERT INTO checkin_exchanges (facet_id, question_text, reply_text, asked_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (_FACET, "domanda di prova", reply),
    )
    conn.commit()


def test_first_observation_adopts_signal_over_null_seed(tmp_path: Path):
    db_path = tmp_path / "relic.db"
    conn = init_db(db_path)
    seed_facets(conn)

    # Precondition mirrors production: seeded trait row with NULL value_position.
    row = conn.execute(
        "SELECT value_position FROM traits WHERE facet_id = ?", (_FACET,)
    ).fetchone()
    assert row is not None and row[0] is None

    _seed_exchange(conn, "mi perdo nelle astrazioni, sono molto filosofica")
    process_pending_exchanges(
        conn, tmp_path / "missing_baseline.json", "subj_test",
        llm_client=_stub_llm(0.8),
    )

    value = conn.execute(
        "SELECT value_position FROM traits WHERE facet_id = ?", (_FACET,)
    ).fetchone()[0]
    conn.close()
    assert value == 0.8  # adopted, not NULL-blended away


def test_second_observation_blends_prior_and_new(tmp_path: Path):
    db_path = tmp_path / "relic.db"
    conn = init_db(db_path)
    seed_facets(conn)

    _seed_exchange(conn, "prima risposta")
    process_pending_exchanges(
        conn, tmp_path / "missing_baseline.json", "subj_test",
        llm_client=_stub_llm(0.8),
    )
    _seed_exchange(conn, "seconda risposta")
    process_pending_exchanges(
        conn, tmp_path / "missing_baseline.json", "subj_test",
        llm_client=_stub_llm(0.3),
    )

    value = conn.execute(
        "SELECT value_position, observation_count FROM traits WHERE facet_id = ?",
        (_FACET,),
    ).fetchone()
    conn.close()
    # 0.7*0.8 + 0.3*0.3 = 0.65
    assert abs(value[0] - 0.65) < 1e-9
    assert value[1] == 2
