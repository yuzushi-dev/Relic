"""Tests for question_engine.select_followup (follow-up-first question lane).

Contract:
- candidate when the latest answered exchange has a reply captured within the
  72h window AND no exchange was asked after that reply;
- None when: no replies, reply too old, thread already followed up, empty reply;
- hint is built from the reply text (not the original question) so the Jaccard
  anti-repeat gate does not collide with the original question text;
- reply excerpt is bounded so the rendered topic block stays within budget.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from relic.checkin.db_init import init_db, seed_facets
from relic.checkin.question_engine import select_followup, _FOLLOWUP_EXCERPT_CHARS


NOW = datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc)


@pytest.fixture()
def conn(tmp_path):
    c = init_db(tmp_path / "relic.db")
    seed_facets(c)
    yield c
    c.close()


def _insert_exchange(
    conn: sqlite3.Connection,
    *,
    asked_at: datetime,
    reply_text: str | None = None,
    reply_captured_at: datetime | None = None,
    facet_id: str = "relational.help_seeking",
    question_text: str = "Come gestisce le situazioni in cui deve chiedere aiuto.",
):
    conn.execute(
        "INSERT INTO checkin_exchanges (facet_id, question_text, asked_at, reply_text, reply_captured_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            facet_id,
            question_text,
            asked_at.isoformat(),
            reply_text,
            reply_captured_at.isoformat() if reply_captured_at else None,
        ),
    )
    conn.commit()


class TestSelectFollowup:
    def test_no_exchanges_returns_none(self, conn):
        assert select_followup(conn, NOW) is None

    def test_unreplied_exchange_returns_none(self, conn):
        _insert_exchange(conn, asked_at=NOW - timedelta(hours=4))
        assert select_followup(conn, NOW) is None

    def test_recent_reply_is_candidate(self, conn):
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(hours=10),
            reply_text="ho chiesto una mano a mio fratello per il trasloco",
            reply_captured_at=NOW - timedelta(hours=9),
        )
        cand = select_followup(conn, NOW)
        assert cand is not None
        assert cand["facet_id"] == "relational.help_seeking"
        assert "trasloco" in cand["hint"]
        assert cand["hint"].startswith("Approfondisci")

    def test_reply_older_than_window_returns_none(self, conn):
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(days=5),
            reply_text="risposta vecchia",
            reply_captured_at=NOW - timedelta(days=4),
        )
        assert select_followup(conn, NOW) is None

    def test_already_followed_up_returns_none(self, conn):
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(hours=20),
            reply_text="una risposta",
            reply_captured_at=NOW - timedelta(hours=19),
        )
        # A newer ask after the reply closes the thread.
        _insert_exchange(conn, asked_at=NOW - timedelta(hours=2))
        assert select_followup(conn, NOW) is None

    def test_followup_of_followup_returns_none(self, conn):
        """Regression: a follow-up exchange must never itself be followed up.
        Without the depth cap, a replied follow-up becomes the new latest
        answered exchange and select_followup would chain on it forever,
        starving TGS facet coverage."""
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(hours=10),
            question_text='Approfondisci quello che ti ha risposto: «ho parlato con mio fratello».',
            reply_text="sì è andata bene, mi ha aiutato molto",
            reply_captured_at=NOW - timedelta(hours=9),
        )
        assert select_followup(conn, NOW) is None

    def test_empty_reply_returns_none(self, conn):
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(hours=10),
            reply_text="   ",
            reply_captured_at=NOW - timedelta(hours=9),
        )
        assert select_followup(conn, NOW) is None

    def test_excerpt_is_bounded(self, conn):
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(hours=10),
            reply_text="parola " * 80,
            reply_captured_at=NOW - timedelta(hours=9),
        )
        cand = select_followup(conn, NOW)
        assert cand is not None
        assert len(cand["reply_excerpt"]) <= _FOLLOWUP_EXCERPT_CHARS

    def test_reply_quote_scaffold_stripped_from_excerpt(self, conn):
        """Regression: the Telegram '[Replying to: "..."]' quote block holds the
        prior turn (Gumi's own diegetic opener). It must not leak into the
        follow-up excerpt, or Gumi asks the subject to elaborate on Gumi's life.
        """
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(hours=10),
            reply_text=(
                '[Replying to: "Sto provando a sistemare l\'ordine delle cartelle '
                'dei miei demo, ma è un caos totale ✨ Ti è capitato di fermarti?"] '
                "Sì ieri ho avuto una discussione con Barbara e l'ho gestita con calma"
            ),
            reply_captured_at=NOW - timedelta(hours=9),
        )
        cand = select_followup(conn, NOW)
        assert cand is not None
        assert "Replying to" not in cand["hint"]
        assert "demo" not in cand["hint"]  # Gumi's life must not be attributed
        assert "Barbara" in cand["hint"]  # the subject's actual words survive

    def test_clarifying_question_reply_skips_followup(self, conn):
        """Regression: a short question-back ("Quale cartelle demo?") is a
        clarification, not an answer. Following up on it propagates a prior
        confusion another hop — must fall back to a fresh facet question (None).
        """
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(hours=10),
            reply_text="Quale cartelle demo? 🤔",
            reply_captured_at=NOW - timedelta(hours=9),
        )
        assert select_followup(conn, NOW) is None

    def test_hint_low_jaccard_with_original_question(self, conn):
        """The hint must be built from the reply, so the anti-repeat gate
        (Jaccard >= 0.60 vs recent question texts) does not block it."""
        from relic.checkin.topic_hint import render_topic_hint

        question = "Come gestisce le situazioni in cui deve chiedere aiuto."
        _insert_exchange(
            conn,
            asked_at=NOW - timedelta(hours=10),
            question_text=question,
            reply_text="di solito provo prima da solo, poi sento un collega",
            reply_captured_at=NOW - timedelta(hours=9),
        )
        cand = select_followup(conn, NOW)
        assert cand is not None
        block = render_topic_hint(cand["hint"], [question])
        assert block != "", "follow-up hint must survive anti-repeat vs the original question"
        assert len(block) <= 200
