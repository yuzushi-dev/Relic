"""Tests for privacy-safe reply valence capture."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from relic.checkin.db_init import init_db as init_checkin_db, seed_facets
from relic.checkin.reply_capture import capture_reply_if_pending
from relic.checkin.valence import score_valence
from relic.db import init_db as init_runtime_db


def _seed_subject(tmp_path: Path, subject_id: str, *, consent: bool) -> Path:
    subject_dir = tmp_path / "subjects" / subject_id
    subject_dir.mkdir(parents=True)
    (subject_dir / "delivery_policy.json").write_text(
        json.dumps({"consent_for_active_elicitation": consent}),
        encoding="utf-8",
    )
    db_path = subject_dir / "relic.db"
    conn = init_checkin_db(db_path)
    try:
        seed_facets(conn)
        conn.execute(
            """INSERT INTO checkin_exchanges (facet_id, question_text, asked_at)
               VALUES (?, ?, ?)""",
            ("cognitive.decision_speed", "Come va ultimamente?", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_score_valence_positive_italian_text():
    assert score_valence("Mi sento molto felice, sereno e contento oggi.") > 0.0


def test_score_valence_positive_italian_affect_phrase():
    assert score_valence("che bello, mi piace tantissimo!") > 0.3


def test_score_valence_negative_italian_text():
    assert score_valence("Sono triste, frustrato e davvero arrabbiato.") < 0.0


def test_score_valence_negative_italian_affect_phrase():
    assert score_valence("che noia, mi sento male e triste") < -0.3


def test_score_valence_neutral_text_is_close_to_zero():
    assert score_valence("") == 0.0
    assert abs(score_valence("Oggi ho preso il treno e poi ho mangiato.")) < 0.2


def test_score_valence_negation_flips_sentiment():
    assert score_valence("Sono felice.") > 0.0
    assert score_valence("Non sono felice.") < 0.0
    assert score_valence("This is not bad at all.") > 0.0
    assert score_valence("non mi piace per niente") < 0.0


def test_score_valence_mild_affirmations_are_not_maximal():
    score = score_valence("ok va bene")
    assert 0.0 <= score <= 0.5


def test_score_valence_emojis_influence_score():
    assert score_valence("Mi sento bene 🙂") > 0.0
    assert score_valence("Che giornata terribile 😞") < 0.0


def test_capture_reply_with_consent_stores_reply_valence(tmp_path: Path):
    db_path = _seed_subject(tmp_path, "s1", consent=True)

    captured = capture_reply_if_pending(
        "Mi sento molto meglio e abbastanza sereno oggi.",
        subject_id="s1",
        relic_home=str(tmp_path),
    )
    assert captured is True

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT reply_text, reply_valence FROM checkin_exchanges",
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "Mi sento molto meglio e abbastanza sereno oggi."
    assert row[1] is not None
    assert row[1] > 0.0


def test_capture_reply_without_consent_keeps_reply_text_and_valence_null(tmp_path: Path):
    db_path = _seed_subject(tmp_path, "s1", consent=False)

    captured = capture_reply_if_pending(
        "Mi sento molto peggio e abbastanza triste oggi.",
        subject_id="s1",
        relic_home=str(tmp_path),
    )
    assert captured is False

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT reply_text, reply_valence FROM checkin_exchanges",
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] is None
    assert row[1] is None


def test_runtime_init_db_adds_reply_valence_column():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_runtime_db(db_path)
        conn = sqlite3.connect(str(db_path))
        try:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(checkin_exchanges)")]
        finally:
            conn.close()

    assert "reply_valence" in columns
