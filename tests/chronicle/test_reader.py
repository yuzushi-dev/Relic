"""Chronicle reader tests, T070 query/timeline/stats coverage."""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest


def _patch_reader_and_emitter(monkeypatch, tmp_relic_db, tmp_chronicle_dir):
    from relic.chronicle import emitter as em
    from relic.chronicle import reader as rd

    def _fake_conn():
        return sqlite3.connect(tmp_relic_db)

    monkeypatch.setattr(em, "_get_db_connection", _fake_conn)
    monkeypatch.setattr(em, "_chronicle_base_dir", lambda: Path(tmp_chronicle_dir))
    monkeypatch.setattr(rd, "_get_db_connection", _fake_conn)


def _seed_events(n: int, *, trace_id=None, subject_id=None, event_type="test_event"):
    from relic.chronicle import emit_event, EventCategory

    ids = []
    for _ in range(n):
        eid = emit_event(
            event_type=event_type,
            event_category=EventCategory.BACKGROUND,
            source_module="tests.chronicle.test_reader",
            trace_id=trace_id,
            subject_id=subject_id,
        )
        ids.append(eid)
    return ids


class TestQueryEvents:
    def test_query_returns_empty_when_no_match(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_reader_and_emitter(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import query_events

        rows = query_events(trace_id=uuid.uuid4())
        assert rows == []

    def test_query_filter_by_trace_id(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_reader_and_emitter(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import query_events

        tid = uuid.uuid4()
        _seed_events(3, trace_id=tid)
        _seed_events(2, trace_id=uuid.uuid4())  # noise

        rows = query_events(trace_id=tid)
        assert len(rows) == 3

    def test_query_filter_by_subject(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_reader_and_emitter(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import query_events

        _seed_events(2, subject_id="subj_a")
        _seed_events(3, subject_id="subj_b")

        rows = query_events(subject_id="subj_b")
        assert len(rows) == 3
        assert all(r["subject_id"] == "subj_b" for r in rows)

    def test_query_filter_by_event_type(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_reader_and_emitter(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import query_events

        _seed_events(2, event_type="model_called")
        _seed_events(1, event_type="memory_read")

        rows = query_events(event_type="model_called")
        assert len(rows) == 2

    def test_query_limit_respected(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_reader_and_emitter(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import query_events

        _seed_events(10)
        rows = query_events(limit=3)
        assert len(rows) == 3


class TestJoinTrace:
    def test_join_trace_groups_events_and_decisions(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_reader_and_emitter(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_decision, join_trace

        tid = uuid.uuid4()
        _seed_events(2, trace_id=tid)
        emit_decision(
            decision_kind="test",
            selected_action={"a": 1},
            actor_type="rule",
            actor_id="r",
            trace_id=tid,
        )

        bundle = join_trace(tid)
        assert bundle["stats"]["events_count"] == 2
        assert bundle["stats"]["decisions_count"] == 1


class TestStats:
    def test_stats_returns_aggregates(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_reader_and_emitter(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import stats

        _seed_events(4)
        s = stats()
        assert s["total_events"] >= 4
        assert "by_event_type" in s
        assert "by_severity" in s
        assert "by_sensitivity" in s
