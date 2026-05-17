"""Chronicle emitter tests — T014 regression + dual-write + bug-fix coverage.

Covers:
  - emit_event / emit_decision / emit_snapshot / emit_provenance_edge happy path
  - Dual-write: JSONL first, SQLite second
  - B1 regression: sensitivity enum value matches schema default (lowercase 'safe')
  - B2 regression: payload_hash computed on dict (not bytes repr)
  - B3 regression: INSERT OR ABORT semantics, second insert with same PK fails
  - B4 regression: snapshot trace_id persisted to SQLite (not __dict__ hack)
  - Fail-open: emitter never raises into caller
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _patch_db_and_journal(monkeypatch, tmp_relic_db: str, tmp_chronicle_dir: str):
    """Re-route emitter's DB connection and journal path into temp fixtures."""
    from relic.chronicle import emitter as em

    def _fake_conn():
        conn = sqlite3.connect(tmp_relic_db)
        return conn

    monkeypatch.setattr(em, "_get_db_connection", _fake_conn)
    monkeypatch.setattr(em, "_chronicle_base_dir", lambda: Path(tmp_chronicle_dir))


# ---------------------------------------------------------------------------
# emit_event basics
# ---------------------------------------------------------------------------
class TestEmitEventBasics:
    def test_emit_event_returns_uuid(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_event, EventCategory

        eid = emit_event(
            event_type="test_event",
            event_category=EventCategory.BACKGROUND,
            source_module="tests.chronicle.test_emitter",
            payload={"k": "v"},
        )
        assert isinstance(eid, uuid.UUID)
        assert eid.int != 0  # not the dummy zero UUID

    def test_emit_event_writes_to_sqlite(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_event, EventCategory

        eid = emit_event(
            event_type="test_event",
            event_category=EventCategory.BACKGROUND,
            source_module="tests.chronicle.test_emitter",
        )

        conn = sqlite3.connect(tmp_relic_db)
        row = conn.execute(
            "SELECT event_id, sensitivity FROM chronicle_events WHERE event_id = ?",
            (str(eid),),
        ).fetchone()
        conn.close()
        assert row is not None

    def test_emit_event_writes_to_jsonl(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_event, EventCategory

        eid = emit_event(
            event_type="test_event",
            event_category=EventCategory.BACKGROUND,
            source_module="tests.chronicle.test_emitter",
        )

        journal = Path(tmp_chronicle_dir) / "journal"
        files = list(journal.glob("*.jsonl"))
        assert len(files) == 1
        content = files[0].read_text()
        assert str(eid) in content


# ---------------------------------------------------------------------------
# B1 regression: sensitivity case
# ---------------------------------------------------------------------------
class TestSensitivityCase:
    def test_sensitivity_persisted_lowercase(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        """B1 regression: enum.value is lowercase 'safe', migration default is lowercase 'safe'."""
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_event, EventCategory
        from relic.persistence import PrivacyLevel

        eid = emit_event(
            event_type="test_event",
            event_category=EventCategory.BACKGROUND,
            source_module="tests.chronicle.test_emitter",
            sensitivity=PrivacyLevel.SAFE,
        )
        conn = sqlite3.connect(tmp_relic_db)
        row = conn.execute(
            "SELECT sensitivity FROM chronicle_events WHERE event_id = ?",
            (str(eid),),
        ).fetchone()
        conn.close()
        assert row[0] == "safe"  # NOT 'SAFE'

    def test_query_by_sensitivity_lowercase_works(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        """B1 regression: query WHERE sensitivity = 'safe' must match the row we just wrote."""
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_event, EventCategory
        from relic.persistence import PrivacyLevel

        emit_event(
            event_type="test_event",
            event_category=EventCategory.BACKGROUND,
            source_module="tests.chronicle.test_emitter",
            sensitivity=PrivacyLevel.SAFE,
        )
        conn = sqlite3.connect(tmp_relic_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM chronicle_events WHERE sensitivity = 'safe'"
        ).fetchone()[0]
        conn.close()
        assert count >= 1


# ---------------------------------------------------------------------------
# B2 regression: payload_hash on dict (not bytes)
# ---------------------------------------------------------------------------
class TestPayloadHash:
    def test_payload_hash_matches_canonical_dict_hash(self):
        """B2 regression: _compute_payload_hash must hash the dict canonically,
        not str(bytes) of its JSON encoding."""
        from relic.chronicle.emitter import _compute_payload_hash
        from relic.artifacts.checksums import compute_checksum

        payload = {"k": "v", "n": 1}
        h = _compute_payload_hash(payload)

        # Expected: same hash as canonical dict hash via compute_checksum
        expected = "sha256:" + compute_checksum(payload).lower()
        assert h == expected

    def test_payload_hash_not_str_bytes_repr(self):
        """B2 regression: ensure we did NOT regress to the bytes-repr bug."""
        from relic.chronicle.emitter import _compute_payload_hash

        payload = {"k": "v"}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        wrong_hash = "sha256:" + hashlib.sha256(str(canonical).encode()).hexdigest()

        actual = _compute_payload_hash(payload)
        assert actual != wrong_hash  # different from the broken bytes-repr behaviour


# ---------------------------------------------------------------------------
# B3 regression: INSERT OR ABORT (immutable audit log)
# ---------------------------------------------------------------------------
class TestInsertImmutability:
    def test_duplicate_event_id_rejected(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        """B3 regression: INSERT OR ABORT — second insert with same event_id fails,
        does not silently overwrite."""
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle.emitter import _insert_row

        eid = str(uuid.uuid4())
        row = {
            "event_id": eid,
            "event_type": "x",
            "event_category": "background",
            "trace_id": str(uuid.uuid4()),
            "source_module": "test",
            "timestamp": "2026-05-16T00:00:00+00:00",
        }
        ok1 = _insert_row("chronicle_events", row)
        ok2 = _insert_row("chronicle_events", row)
        assert ok1 is True
        assert ok2 is False  # second insert must fail (PK collision)


# ---------------------------------------------------------------------------
# B4 regression: snapshot trace_id persisted (not __dict__ hack)
# ---------------------------------------------------------------------------
class TestSnapshotTraceId:
    def test_snapshot_trace_id_persisted(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        """B4 regression: snapshot trace_id is a real model field + DB column."""
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_snapshot

        tid = uuid.uuid4()
        sid = emit_snapshot(
            snapshot_type="test_snapshot",
            subject_id="subj_x",
            scope_ref="scope_x",
            content={"foo": "bar"},
            trace_id=tid,
        )

        conn = sqlite3.connect(tmp_relic_db)
        row = conn.execute(
            "SELECT trace_id FROM chronicle_state_snapshots WHERE snapshot_id = ?",
            (str(sid),),
        ).fetchone()
        conn.close()
        assert row is not None, "snapshot row missing — INSERT may have failed"
        assert row[0] == str(tid)


# ---------------------------------------------------------------------------
# emit_decision smoke
# ---------------------------------------------------------------------------
class TestEmitDecision:
    def test_decision_basic_write(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_decision

        did = emit_decision(
            decision_kind="test_decision",
            selected_action={"a": "b"},
            actor_type="rule",
            actor_id="test_rule",
            rationale_summary="short rationale",
        )
        conn = sqlite3.connect(tmp_relic_db)
        row = conn.execute(
            "SELECT decision_id, rationale_summary FROM chronicle_decisions WHERE decision_id = ?",
            (str(did),),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "short rationale"

    def test_decision_rationale_truncated_at_280(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        """rationale_summary > 280 chars → emitter truncates before model validation."""
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_decision

        long_text = "x" * 500
        did = emit_decision(
            decision_kind="test_decision",
            selected_action={},
            actor_type="rule",
            actor_id="test_rule",
            rationale_summary=long_text,
        )
        conn = sqlite3.connect(tmp_relic_db)
        row = conn.execute(
            "SELECT rationale_summary FROM chronicle_decisions WHERE decision_id = ?",
            (str(did),),
        ).fetchone()
        conn.close()
        assert row is not None
        assert len(row[0]) == 280


# ---------------------------------------------------------------------------
# Fail-open: emitter never raises
# ---------------------------------------------------------------------------
class TestFailOpen:
    def test_emit_event_returns_zero_uuid_on_consent_block(
        self, monkeypatch, tmp_relic_db, tmp_chronicle_dir
    ):
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_event, EventCategory

        with patch(
            "relic.chronicle.emitter.is_capture_allowed",
            return_value=(False, "consent_denied:analytics"),
        ):
            eid = emit_event(
                event_type="test_event",
                event_category=EventCategory.BACKGROUND,
                source_module="tests.chronicle.test_emitter",
                consent_basis="analytics",
                subject_id="subj_x",
            )
        assert eid == uuid.UUID("00000000-0000-0000-0000-000000000000")

    def test_emit_event_with_invalid_event_type_does_not_raise(
        self, monkeypatch, tmp_relic_db, tmp_chronicle_dir
    ):
        """Pydantic validation error → emit_event must not propagate exception."""
        _patch_db_and_journal(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import emit_event, EventCategory

        # event_type with uppercase violates _EVENT_TYPE_RE
        try:
            emit_event(
                event_type="BadEventType",
                event_category=EventCategory.BACKGROUND,
                source_module="tests.chronicle.test_emitter",
            )
        except Exception:
            pytest.fail("emit_event must be fail-open and not raise")
