"""Tests for relic.checkin.context_builder.

Contract:
- build_deliver_context returns "" when hermes_home is None
- build_recent_checkins_section parses MEMORY.md, filters by checkin job ID
- build_observations_section reads relic.db observations (consent-gated externally)
- build_topic_hint_section is skipped when DB absent
- build_style_hints_section returns "" when bl_path absent
- build_avatar_section reads AVATAR_SPEC.md, caps at 600 chars
- consent gate: observations/topic/style skipped when consent False
- all sections fail-open: exceptions return ""
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from relic.checkin.context_builder import (
    build_avatar_section,
    build_deliver_context,
    build_observations_section,
    build_recent_checkins_section,
    build_recent_subject_messages_section,
    build_style_hints_section,
    build_topic_hint_section,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hermes_home(tmp_path: Path) -> Path:
    hp = tmp_path / "hermes"
    hp.mkdir()
    return hp


@pytest.fixture
def relic_dir(tmp_path: Path) -> Path:
    rd = tmp_path / "relic"
    subject_dir = rd / "subjects" / "test_subj"
    subject_dir.mkdir(parents=True)
    return rd


def _write_consent(relic_dir: Path, active: bool) -> None:
    dp = relic_dir / "subjects" / "test_subj" / "delivery_policy.json"
    dp.write_text(json.dumps({"consent_for_active_elicitation": active}), encoding="utf-8")


def _init_db(relic_dir: Path) -> sqlite3.Connection:
    from relic.checkin.db_init import init_db, seed_facets

    db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
    conn = init_db(db_path)
    seed_facets(conn)
    return conn


# ---------------------------------------------------------------------------
# build_deliver_context — top-level gates
# ---------------------------------------------------------------------------


class TestBuildDeliverContextGates:
    def test_no_hermes_home_returns_empty(self, relic_dir: Path):
        _write_consent(relic_dir, active=True)
        result = build_deliver_context(
            "test_subj", hermes_home=None, relic_home=relic_dir
        )
        assert result == ""

    def test_consent_false_skips_consent_sections(
        self, hermes_home: Path, relic_dir: Path
    ):
        _write_consent(relic_dir, active=False)
        conn = _init_db(relic_dir)
        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        conn.execute(
            "INSERT INTO observations (facet_id, source_type, content, created_at) "
            "VALUES (?, 'checkin_reply', 'osservazione recente', datetime('now'))",
            ("cognitive.decision_speed",),
        )
        conn.commit()
        conn.close()

        result = build_deliver_context(
            "test_subj", hermes_home=hermes_home, relic_home=relic_dir
        )
        assert "osservazione recente" not in result
        assert "ho imparato" not in result

    def test_consent_true_includes_observations(
        self, hermes_home: Path, relic_dir: Path
    ):
        _write_consent(relic_dir, active=True)
        conn = _init_db(relic_dir)
        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        conn.execute(
            "INSERT INTO observations (facet_id, source_type, content, created_at) "
            "VALUES (?, 'checkin_reply', 'preferisce comunicazione diretta', datetime('now'))",
            ("cognitive.decision_speed",),
        )
        conn.commit()
        conn.close()

        result = build_deliver_context(
            "test_subj", hermes_home=hermes_home, relic_home=relic_dir
        )
        assert "preferisce comunicazione diretta" in result

    def test_avatar_included_without_consent(
        self, hermes_home: Path, relic_dir: Path
    ):
        _write_consent(relic_dir, active=False)
        avatar_path = hermes_home / "AVATAR_SPEC.md"
        avatar_path.write_text("Capelli neri, occhi verdi.", encoding="utf-8")

        result = build_deliver_context(
            "test_subj", hermes_home=hermes_home, relic_home=relic_dir
        )
        assert "Capelli neri" in result


# ---------------------------------------------------------------------------
# build_recent_checkins_section
# ---------------------------------------------------------------------------


class TestBuildRecentCheckinsSection:
    def test_no_memory_md_returns_empty(self, hermes_home: Path):
        assert build_recent_checkins_section(hermes_home) == ""

    def test_parses_memory_block(self, hermes_home: Path):
        mem = hermes_home / "MEMORY.md"
        mem.write_text(
            "<!-- gumi:memory_sync:begin -->\n"
            "### 2026-05-17 10:00 (job=abc123)\n"
            "> Ciao, come stai oggi?\n"
            "<!-- gumi:memory_sync:end -->\n",
            encoding="utf-8",
        )
        result = build_recent_checkins_section(hermes_home)
        assert "Ciao, come stai oggi?" in result
        assert "messaggi recenti" in result

    def test_filters_by_job_id(self, hermes_home: Path):
        jobs_dir = hermes_home / "cron"
        jobs_dir.mkdir()
        (jobs_dir / "jobs.json").write_text(
            json.dumps({"jobs": [{"id": "job-checkin-01", "script": "checkin_message"}]}),
            encoding="utf-8",
        )
        mem = hermes_home / "MEMORY.md"
        mem.write_text(
            "<!-- gumi:memory_sync:begin -->\n"
            "### 2026-05-17 10:00 (job=job-checkin-01)\n"
            "> Messaggio del checkin\n"
            "### 2026-05-16 09:00 (job=other-job-99)\n"
            "> Messaggio di altro job\n"
            "<!-- gumi:memory_sync:end -->\n",
            encoding="utf-8",
        )
        result = build_recent_checkins_section(hermes_home)
        assert "Messaggio del checkin" in result
        assert "Messaggio di altro job" not in result

    def test_skips_silent_lines(self, hermes_home: Path):
        mem = hermes_home / "MEMORY.md"
        mem.write_text(
            "<!-- gumi:memory_sync:begin -->\n"
            "### 2026-05-17 10:00 (job=j1)\n"
            "> [SILENT]\n"
            "<!-- gumi:memory_sync:end -->\n",
            encoding="utf-8",
        )
        result = build_recent_checkins_section(hermes_home)
        assert result == ""

    def test_returns_last_5(self, hermes_home: Path):
        entries = "\n".join(
            f"### 2026-05-1{i} 10:00 (job=j1)\n> Messaggio numero {i}"
            for i in range(1, 9)  # 8 entries
        )
        mem = hermes_home / "MEMORY.md"
        mem.write_text(
            f"<!-- gumi:memory_sync:begin -->\n{entries}\n<!-- gumi:memory_sync:end -->\n",
            encoding="utf-8",
        )
        result = build_recent_checkins_section(hermes_home)
        # Only last 5 should appear (4..8)
        assert "numero 4" in result
        assert "numero 1" not in result

    def test_malformed_memory_returns_empty(self, hermes_home: Path):
        (hermes_home / "MEMORY.md").write_text("no block here", encoding="utf-8")
        assert build_recent_checkins_section(hermes_home) == ""


# ---------------------------------------------------------------------------
# build_observations_section
# ---------------------------------------------------------------------------


class TestBuildObservationsSection:
    def test_no_db_returns_empty(self, tmp_path: Path):
        result = build_observations_section(tmp_path / "nonexistent.db")
        assert result == ""

    def test_empty_observations_returns_empty(self, relic_dir: Path):
        conn = _init_db(relic_dir)
        conn.close()
        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        result = build_observations_section(db_path)
        assert result == ""

    def test_returns_observations(self, relic_dir: Path):
        conn = _init_db(relic_dir)
        conn.execute(
            "INSERT INTO observations (facet_id, source_type, content, created_at) "
            "VALUES (?, 'checkin_reply', 'ama leggere di notte', datetime('now'))",
            ("cognitive.decision_speed",),
        )
        conn.commit()
        conn.close()
        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        result = build_observations_section(db_path)
        assert "ama leggere di notte" in result
        assert "ho imparato" in result

    def test_ignores_non_checkin_source(self, relic_dir: Path):
        conn = _init_db(relic_dir)
        conn.execute(
            "INSERT INTO observations (facet_id, source_type, content, created_at) "
            "VALUES (?, 'manual', 'nota manuale', datetime('now'))",
            ("cognitive.decision_speed",),
        )
        conn.commit()
        conn.close()
        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        result = build_observations_section(db_path)
        assert "nota manuale" not in result

    def test_truncates_long_content(self, relic_dir: Path):
        conn = _init_db(relic_dir)
        long_obs = "X" * 300
        conn.execute(
            "INSERT INTO observations (facet_id, source_type, content, created_at) "
            "VALUES (?, 'checkin_reply', ?, datetime('now'))",
            ("cognitive.decision_speed", long_obs),
        )
        conn.commit()
        conn.close()
        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        result = build_observations_section(db_path)
        assert "X" * 120 in result
        assert "X" * 121 not in result


# ---------------------------------------------------------------------------
# build_style_hints_section
# ---------------------------------------------------------------------------


class TestBuildStyleHintsSection:
    def test_no_bl_path_returns_empty(self, tmp_path: Path):
        result = build_style_hints_section(tmp_path / "nope.json")
        assert result == ""

    def test_returns_hint_when_low_humor(self, tmp_path: Path):
        bl = {
            "interaction": {
                "humor_tolerance": {
                    "value": 0.2,
                    "confidence": "medium",
                    "correction_state": "active",
                }
            }
        }
        bl_path = tmp_path / "subject_baseline.json"
        bl_path.write_text(json.dumps(bl), encoding="utf-8")
        result = build_style_hints_section(bl_path)
        assert "ironia" in result

    def test_no_bullets_returns_empty(self, tmp_path: Path):
        bl = {"interaction": {}}
        bl_path = tmp_path / "subject_baseline.json"
        bl_path.write_text(json.dumps(bl), encoding="utf-8")
        result = build_style_hints_section(bl_path)
        assert result == ""


# ---------------------------------------------------------------------------
# build_avatar_section
# ---------------------------------------------------------------------------


class TestBuildAvatarSection:
    def test_no_file_returns_empty(self, tmp_path: Path):
        assert build_avatar_section(tmp_path) == ""

    def test_returns_avatar_text(self, tmp_path: Path):
        (tmp_path / "AVATAR_SPEC.md").write_text("Capelli scuri.", encoding="utf-8")
        result = build_avatar_section(tmp_path)
        assert "Capelli scuri." in result
        assert "aspetto di Gumi" in result

    def test_caps_at_600(self, tmp_path: Path):
        (tmp_path / "AVATAR_SPEC.md").write_text("A" * 1000, encoding="utf-8")
        result = build_avatar_section(tmp_path)
        assert "A" * 600 in result
        assert "A" * 601 not in result

    def test_empty_file_returns_empty(self, tmp_path: Path):
        (tmp_path / "AVATAR_SPEC.md").write_text("", encoding="utf-8")
        assert build_avatar_section(tmp_path) == ""


# ---------------------------------------------------------------------------
# build_topic_hint_section
# ---------------------------------------------------------------------------


class TestBuildTopicHintSection:
    def test_no_db_returns_empty(self, tmp_path: Path):
        result = build_topic_hint_section(
            "test_subj", tmp_path / "nope.db", tmp_path / "nope.json"
        )
        assert result == ""

    def test_with_seeded_db_returns_block_or_empty(self, relic_dir: Path):
        """With a valid DB, either returns a topic block or empty (no crash)."""
        conn = _init_db(relic_dir)
        conn.close()
        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"
        result = build_topic_hint_section(
            "test_subj",
            db_path,
            relic_dir / "subjects" / "test_subj" / "subject_baseline.json",
        )
        assert isinstance(result, str)

    def test_inserts_exchange_when_hint_produced(self, relic_dir: Path):
        """If topic_block produced, exchange row is written to DB."""
        conn = _init_db(relic_dir)
        conn.close()
        db_path = relic_dir / "subjects" / "test_subj" / "relic.db"

        result = build_topic_hint_section(
            "test_subj",
            db_path,
            relic_dir / "subjects" / "test_subj" / "subject_baseline.json",
        )
        if result:  # only assert if a hint was actually generated
            check = sqlite3.connect(str(db_path))
            rows = check.execute("SELECT id FROM checkin_exchanges").fetchall()
            check.close()
            assert len(rows) >= 1


# ---------------------------------------------------------------------------
# build_recent_subject_messages_section
# ---------------------------------------------------------------------------


def _init_hermes_state_db(hermes_home: Path, rows: list[tuple[str, float, str]]) -> None:
    """Seed state.db with messages rows (role, timestamp, content)."""
    db_path = hermes_home / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_call_id TEXT,
            tool_calls TEXT,
            tool_name TEXT,
            timestamp REAL NOT NULL,
            token_count INTEGER,
            finish_reason TEXT,
            reasoning TEXT,
            reasoning_content TEXT,
            reasoning_details TEXT,
            codex_reasoning_items TEXT,
            codex_message_items TEXT
        )"""
    )
    conn.execute("INSERT OR IGNORE INTO sessions(id) VALUES (?)", ("s1",))
    for role, ts, content in rows:
        conn.execute(
            "INSERT INTO messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            ("s1", role, content, ts),
        )
    conn.commit()
    conn.close()


class TestBuildRecentSubjectMessagesSection:
    def test_no_state_db_returns_empty(self, hermes_home: Path):
        assert build_recent_subject_messages_section(hermes_home) == ""

    def test_only_user_messages_within_window(self, hermes_home: Path):
        from datetime import datetime, timezone
        now_ts = datetime.now(timezone.utc).timestamp()
        rows = [
            ("user", now_ts - 600, "Ciao, oggi sto bene"),
            ("assistant", now_ts - 500, "Bene Daniele, qui c'è il sole"),
            ("user", now_ts - 400, "Mi piace questa giornata"),
            ("user", now_ts - 999999, "vecchio fuori finestra"),
        ]
        _init_hermes_state_db(hermes_home, rows)
        block = build_recent_subject_messages_section(hermes_home, hours=24)
        assert "Ciao, oggi sto bene" in block
        assert "Mi piace questa giornata" in block
        assert "vecchio fuori finestra" not in block
        assert "qui c'è il sole" not in block

    def test_filters_cron_prompt_injections(self, hermes_home: Path):
        from datetime import datetime, timezone
        now_ts = datetime.now(timezone.utc).timestamp()
        rows = [
            ("user", now_ts - 100, "[IMPORTANT: You are running as a scheduled cron job. ... DELIVER tipo: text]"),
            ("user", now_ts - 50, "Vero messaggio del soggetto"),
        ]
        _init_hermes_state_db(hermes_home, rows)
        block = build_recent_subject_messages_section(hermes_home, hours=24)
        assert "Vero messaggio del soggetto" in block
        assert "scheduled cron job" not in block

    def test_strips_reply_to_quote_prefix(self, hermes_home: Path):
        from datetime import datetime, timezone
        now_ts = datetime.now(timezone.utc).timestamp()
        rows = [
            (
                "user",
                now_ts - 100,
                '[Replying to: "Stamattina è bella"]\n\nGrazie, anche per me',
            ),
        ]
        _init_hermes_state_db(hermes_home, rows)
        block = build_recent_subject_messages_section(hermes_home, hours=24)
        assert "Grazie, anche per me" in block
        assert "Replying to" not in block

    def test_no_messages_returns_empty(self, hermes_home: Path):
        _init_hermes_state_db(hermes_home, [])
        assert build_recent_subject_messages_section(hermes_home) == ""

    def test_section_header_present(self, hermes_home: Path):
        from datetime import datetime, timezone
        now_ts = datetime.now(timezone.utc).timestamp()
        _init_hermes_state_db(hermes_home, [("user", now_ts - 100, "ok")])
        block = build_recent_subject_messages_section(hermes_home)
        assert "--- cosa ti ha detto di recente" in block
