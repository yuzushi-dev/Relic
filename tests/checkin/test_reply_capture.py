"""Tests for relic.checkin.reply_capture.

Contract:
- capture_reply_if_pending returns False when consent missing/False
- returns False when no pending exchange in time window
- returns False for non-substantive messages (too short, dismissal tokens)
- returns False when exchange has facet_id IS NULL (would orphan in facet_updater)
- returns True and writes reply_text when all conditions met
- idempotent: second call on same exchange returns False (already has reply)
- UPDATE uses WHERE reply_text IS NULL to prevent overwrite race
- reply_captured_at is a parseable UTC ISO-8601 timestamp
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relic.checkin.reply_capture import capture_reply_if_pending, REPLY_WINDOW_HOURS, _is_substantive


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def relic_dir(tmp_path: Path):
    """Minimal relic_home with one subject."""
    subject_dir = tmp_path / "subjects" / "test_subj"
    subject_dir.mkdir(parents=True)
    return tmp_path


def _write_consent(relic_dir: Path, active: bool):
    dp = relic_dir / "subjects" / "test_subj" / "delivery_policy.json"
    dp.write_text(json.dumps({"consent_for_active_elicitation": active}), encoding="utf-8")


def _init_db(relic_dir: Path) -> sqlite3.Connection:
    from relic.checkin.db_init import init_db, seed_facets
    db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
    conn = init_db(db_path)
    seed_facets(conn)
    return conn


def _insert_exchange(
    conn: sqlite3.Connection,
    asked_at: str,
    reply_text: str | None = None,
    facet_id: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO checkin_exchanges (facet_id, question_text, reply_text, asked_at) VALUES (?, ?, ?, ?)",
        (facet_id, "Come gestisci le situazioni di stress?", reply_text, asked_at),
    )
    conn.commit()
    return cur.lastrowid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_ago(h: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


# ---------------------------------------------------------------------------
# _is_substantive
# ---------------------------------------------------------------------------

class TestIsSubstantive:
    def test_long_message_substantive(self):
        assert _is_substantive("Mi capita spesso di sentirmi sopraffatto dal lavoro") is True

    def test_too_short(self):
        assert _is_substantive("ok") is False

    def test_dismissal_token(self):
        assert _is_substantive("[silent]") is False
        assert _is_substantive("no") is False
        assert _is_substantive("boh") is False
        assert _is_substantive("mah") is False

    def test_dismissal_with_trailing_punctuation(self):
        assert _is_substantive("ok!") is False
        assert _is_substantive("no.") is False

    def test_non_dismissal_min_len(self):
        assert _is_substantive("nono") is True  # 4 chars, not in dismissal set

    def test_rejects_cron_scaffold_prompt(self):
        # Under a no-agent cron the delivery turn's prompt was being captured as
        # the subject reply; it must be rejected.
        scaffold = (
            "[IMPORTANT: You are running as a scheduled cron job. DELIVERY: Your "
            "final response will be automatically delivered to the user — do NOT "
            "use send_message or try to call tools.]"
        )
        assert _is_substantive(scaffold) is False

    def test_rejects_proactive_gate_prompt(self):
        assert _is_substantive("Sei Gumi. Il gate mostra DELIVER con tipo, ora e contesto.") is False

    def test_genuine_reply_still_substantive(self):
        assert _is_substantive(
            "Bella domanda, non saprei. Di certo ho un bias a stimare le tempistiche."
        ) is True

    def test_exactly_min_len(self):
        assert _is_substantive("a" * 3) is True

    def test_below_min_len(self):
        assert _is_substantive("a" * 2) is False


# ---------------------------------------------------------------------------
# Consent gate
# ---------------------------------------------------------------------------

class TestConsentGate:
    def test_no_delivery_policy_returns_false(self, relic_dir: Path):
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()
        result = capture_reply_if_pending(
            "Risposta valida e abbastanza lunga",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is False

    def test_consent_false_returns_false(self, relic_dir: Path):
        _write_consent(relic_dir, active=False)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()
        result = capture_reply_if_pending(
            "Risposta valida e abbastanza lunga",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is False

    def test_consent_true_allows_capture(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()
        result = capture_reply_if_pending(
            "Risposta abbastanza lunga per essere valida",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is True


# ---------------------------------------------------------------------------
# Time window
# ---------------------------------------------------------------------------

class TestTimeWindow:
    def test_exchange_within_window_captured(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _hours_ago(REPLY_WINDOW_HOURS / 2), facet_id="cognitive.decision_speed")
        conn.close()
        result = capture_reply_if_pending(
            "Risposta abbastanza lunga per essere valida",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is True

    def test_exchange_outside_window_not_captured(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _hours_ago(REPLY_WINDOW_HOURS + 1), facet_id="cognitive.decision_speed")
        conn.close()
        result = capture_reply_if_pending(
            "Risposta abbastanza lunga per essere valida",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is False

    def test_no_pending_exchange_returns_false(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        conn.close()
        result = capture_reply_if_pending(
            "Risposta abbastanza lunga per essere valida",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is False


# ---------------------------------------------------------------------------
# Write correctness
# ---------------------------------------------------------------------------

class TestWriteCorrectness:
    def test_writes_reply_text(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        exchange_id = _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()

        msg = "Quando sono stressato tendo a isolarmi e a lavorare di più."
        result = capture_reply_if_pending(msg, "test_subj", relic_home=str(relic_dir))
        assert result is True

        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT reply_text, reply_captured_at FROM checkin_exchanges WHERE id = ?",
            (exchange_id,),
        ).fetchone()
        check_conn.close()

        assert row is not None
        assert row[0] == msg
        assert row[1] is not None

    def test_reply_captured_at_is_utc_iso8601(self, relic_dir: Path):
        """reply_captured_at must be a parseable UTC-aware ISO-8601 timestamp."""
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        exchange_id = _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()

        capture_reply_if_pending(
            "Risposta abbastanza lunga per essere valida", "test_subj", relic_home=str(relic_dir)
        )

        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT reply_captured_at FROM checkin_exchanges WHERE id = ?", (exchange_id,)
        ).fetchone()
        check_conn.close()

        ts = datetime.fromisoformat(row[0])
        assert ts.tzinfo is not None  # UTC-aware

    def test_picks_most_recent_pending(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _hours_ago(3), facet_id="cognitive.decision_speed")   # older
        newer_id = _insert_exchange(conn, _hours_ago(1), facet_id="cognitive.risk_tolerance")   # more recent
        conn.close()

        msg = "Risposta abbastanza lunga e valida per il test di cattura"
        capture_reply_if_pending(msg, "test_subj", relic_home=str(relic_dir))

        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT reply_text FROM checkin_exchanges WHERE id = ?", (newer_id,)
        ).fetchone()
        check_conn.close()
        assert row[0] == msg

    def test_idempotent_second_call_returns_false(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()

        msg = "Risposta abbastanza lunga e valida per il test di cattura"
        first = capture_reply_if_pending(msg, "test_subj", relic_home=str(relic_dir))
        second = capture_reply_if_pending("Altro messaggio diverso e lungo abbastanza", "test_subj", relic_home=str(relic_dir))
        assert first is True
        assert second is False  # exchange already has reply_text

    def test_truncates_long_message(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()

        msg = "A" * 3000
        capture_reply_if_pending(msg, "test_subj", relic_home=str(relic_dir))

        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute("SELECT reply_text FROM checkin_exchanges").fetchone()
        check_conn.close()
        assert len(row[0]) == 2000
        assert row[0].endswith("…")

    def test_already_answered_exchange_skipped(self, relic_dir: Path):
        """Exchange that already has reply_text is not overwritten."""
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), reply_text="risposta precedente già salvata qui", facet_id="cognitive.decision_speed")
        conn.close()

        result = capture_reply_if_pending(
            "Risposta abbastanza lunga e valida per il test",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is False

    def test_facet_id_null_not_captured(self, relic_dir: Path):
        """Exchange with null facet_id is skipped — would orphan in facet_updater."""
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id=None)
        conn.close()

        result = capture_reply_if_pending(
            "Risposta abbastanza lunga e valida per il test",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is False

        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute("SELECT reply_text FROM checkin_exchanges").fetchone()
        check_conn.close()
        assert row[0] is None  # not written

    def test_truncates_multibyte_message(self, relic_dir: Path):
        """UTF-8 multibyte chars truncated by code point, not byte."""
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()

        msg = "à" * 3000  # 2-byte UTF-8 per char
        capture_reply_if_pending(msg, "test_subj", relic_home=str(relic_dir))

        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute("SELECT reply_text FROM checkin_exchanges").fetchone()
        check_conn.close()
        assert len(row[0]) == 2000
        assert row[0].endswith("…")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_missing_db_returns_false(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        # No DB created
        result = capture_reply_if_pending(
            "Risposta abbastanza lunga e valida per il test",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is False

    def test_invalid_subject_id_returns_false(self, tmp_path: Path):
        result = capture_reply_if_pending(
            "Risposta abbastanza lunga e valida per il test",
            "",
            relic_home=str(tmp_path),
        )
        assert result is False

    def test_malformed_delivery_policy_returns_false(self, relic_dir: Path):
        """Malformed delivery_policy.json returns False without raising."""
        dp = relic_dir / "subjects" / "test_subj" / "delivery_policy.json"
        dp.write_text("not valid json", encoding="utf-8")
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()
        result = capture_reply_if_pending(
            "Risposta abbastanza lunga e valida per il test",
            "test_subj",
            relic_home=str(relic_dir),
        )
        assert result is False


# ---------------------------------------------------------------------------
# sync_turn integration
# ---------------------------------------------------------------------------

class TestSyncTurnWiring:
    def test_sync_turn_captures_reply_when_consent(self, relic_dir: Path):
        """sync_turn consent-gated carve-out: reply captured in relic.db when consent True."""
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        exchange_id = _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()

        from relic.hermes_plugin.memory_provider import RelicMemoryProvider
        provider = RelicMemoryProvider(
            subject_id="test_subj",
            relic_home=str(relic_dir),
        )
        msg = "Risposta lunga abbastanza per essere catturata da sync_turn"
        provider.sync_turn(msg, "risposta gumi qualsiasi")

        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute(
            "SELECT reply_text FROM checkin_exchanges WHERE id = ?", (exchange_id,)
        ).fetchone()
        check_conn.close()
        assert row[0] == msg

    def test_sync_turn_no_capture_without_consent(self, relic_dir: Path):
        """sync_turn does not capture when consent is False."""
        _write_consent(relic_dir, active=False)
        conn = _init_db(relic_dir)
        _insert_exchange(conn, _now(), facet_id="cognitive.decision_speed")
        conn.close()

        from relic.hermes_plugin.memory_provider import RelicMemoryProvider
        provider = RelicMemoryProvider(
            subject_id="test_subj",
            relic_home=str(relic_dir),
        )
        provider.sync_turn("Risposta lunga abbastanza per essere catturata", "risposta gumi")

        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        check_conn = sqlite3.connect(str(db_path))
        row = check_conn.execute("SELECT reply_text FROM checkin_exchanges").fetchone()
        check_conn.close()
        assert row[0] is None

    def test_empty_subject_id_raises(self):
        """RelicMemoryProvider hard guard: empty or whitespace-only subject_id raises ValueError."""
        from relic.hermes_plugin.memory_provider import RelicMemoryProvider
        with pytest.raises(ValueError, match="subject_id"):
            RelicMemoryProvider(subject_id="")
        with pytest.raises(ValueError, match="subject_id"):
            RelicMemoryProvider(subject_id="   ")
