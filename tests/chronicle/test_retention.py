"""Chronicle retention tests — T022 reaper + archive + delete cascade."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir):
    from relic.chronicle import emitter as em
    from relic.chronicle import retention as rt

    def _fake_conn():
        return sqlite3.connect(tmp_relic_db)

    monkeypatch.setattr(em, "_get_db_connection", _fake_conn)
    monkeypatch.setattr(em, "_chronicle_base_dir", lambda: Path(tmp_chronicle_dir))
    monkeypatch.setattr(rt, "_get_db_connection", _fake_conn)


def _insert_event_with_timestamp(db_path, *, retention_policy="ephemeral", timestamp=None, subject_id=None):
    """Insert event directly with arbitrary timestamp for retention testing."""
    eid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO chronicle_events (event_id, event_type, event_category, trace_id, source_module, timestamp, retention_policy, subject_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (eid, "test", "background", tid, "test", timestamp, retention_policy, subject_id),
    )
    conn.commit()
    conn.close()
    return eid


class TestArchiveJournal:
    def test_archive_dry_run_returns_zero_when_empty(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import archive_journal

        result = archive_journal(dry_run=True)
        assert result["journal_size_bytes"] == 0
        assert result["lines_count"] == 0
        assert result["archived"] is False

    def test_archive_counts_lines(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_event, archive_journal, EventCategory

        for _ in range(3):
            emit_event(
                event_type="test_event",
                event_category=EventCategory.BACKGROUND,
                source_module="tests.chronicle.test_retention",
            )

        result = archive_journal(dry_run=True)
        assert result["lines_count"] == 3
        assert result["journal_size_bytes"] > 0


class TestDeleteExpired:
    def test_dry_run_does_not_delete(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import delete_expired

        # Insert old ephemeral event (2h ago, ephemeral expires at 1h)
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        _insert_event_with_timestamp(tmp_relic_db, retention_policy="ephemeral", timestamp=old_ts)

        result = delete_expired(dry_run=True, policy="ephemeral")
        assert result["chronicle_events_deleted"] == 1

        # Verify NOT actually deleted
        conn = sqlite3.connect(tmp_relic_db)
        cnt = conn.execute("SELECT COUNT(*) FROM chronicle_events").fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_real_delete_removes_expired(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import delete_expired

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        _insert_event_with_timestamp(tmp_relic_db, retention_policy="ephemeral", timestamp=old_ts)

        delete_expired(dry_run=False, policy="ephemeral")

        conn = sqlite3.connect(tmp_relic_db)
        cnt = conn.execute("SELECT COUNT(*) FROM chronicle_events").fetchone()[0]
        conn.close()
        assert cnt == 0

    def test_non_expired_not_deleted(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import delete_expired

        # Recent ephemeral event (5 min ago) — not yet expired
        recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        _insert_event_with_timestamp(tmp_relic_db, retention_policy="ephemeral", timestamp=recent_ts)

        delete_expired(dry_run=False, policy="ephemeral")

        conn = sqlite3.connect(tmp_relic_db)
        cnt = conn.execute("SELECT COUNT(*) FROM chronicle_events").fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_legal_hold_never_deleted(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import delete_expired

        old_ts = (datetime.now(timezone.utc) - timedelta(days=1000)).isoformat()
        _insert_event_with_timestamp(tmp_relic_db, retention_policy="legal_hold", timestamp=old_ts)

        result = delete_expired(dry_run=False)

        conn = sqlite3.connect(tmp_relic_db)
        cnt = conn.execute("SELECT COUNT(*) FROM chronicle_events").fetchone()[0]
        conn.close()
        assert cnt == 1  # not deleted

    def test_subject_id_filter(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        """Regression: subject_id param order bug (was placeholder/value misalignment)."""
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import delete_expired

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        _insert_event_with_timestamp(
            tmp_relic_db, retention_policy="ephemeral", timestamp=old_ts, subject_id="target"
        )
        _insert_event_with_timestamp(
            tmp_relic_db, retention_policy="ephemeral", timestamp=old_ts, subject_id="other"
        )

        delete_expired(dry_run=False, policy="ephemeral", subject_id="target")

        conn = sqlite3.connect(tmp_relic_db)
        rows = conn.execute("SELECT subject_id FROM chronicle_events").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "other"


class TestReaperRun:
    def test_run_returns_summary(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import reaper_run

        result = reaper_run(dry_run=True)
        assert "dry_run" in result
        assert "total_deleted" in result
        assert "summary" in result


class TestSubjectPurge:
    def test_purge_subject_records_cascades_provenance_edges(
        self, monkeypatch, tmp_relic_db, tmp_chronicle_dir
    ):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle.retention import purge_subject_records

        conn = sqlite3.connect(tmp_relic_db)
        conn.execute(
            """
            INSERT INTO chronicle_events
            (event_id, event_type, event_category, trace_id, source_module, timestamp, subject_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event_subject",
                "message",
                "message",
                "trace_subject",
                "test",
                "2026-05-20T00:00:00Z",
                "subj_a",
            ),
        )
        conn.execute(
            """
            INSERT INTO chronicle_provenance_edges
            (edge_id, trace_id, artifact_id, from_node_type, from_node_id, relation, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "edge_subject",
                "trace_subject",
                "artifact_a",
                "event",
                "event_subject",
                "wasGeneratedBy",
                "2026-05-20T00:00:00Z",
            ),
        )
        conn.commit()
        conn.close()

        result = purge_subject_records("subj_a", cascade=True)

        assert result["chronicle_events_deleted"] == 1
        assert result["chronicle_provenance_edges_deleted"] == 1
