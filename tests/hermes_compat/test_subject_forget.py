"""Fix G: GDPR Art. 17 hard delete — relic subject forget.

Tests use ONLY synthetic data (tmp_path). Never touch real RELIC_HOME.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.shared_continuity.service import (
    ContinuityMarker,
    ContinuityService,
    MarkerStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_marker(subject_id: str, marker_id: str = "m1") -> ContinuityMarker:
    return ContinuityMarker(
        marker_id=marker_id,
        subject_id=subject_id,
        gumi_instance_id="g1",
        hermes_profile_id="h1",
        subject_confirmation=True,
        source_type="test",
        created_at="2026-01-01T00:00:00Z",
        subject_words=["ciao"],
        gumi_agreed_words=[],
        raw_source_text=None,
        status=MarkerStatus.ACTIVE,
        gumi_recall_allowed=True,
        recall_count=0,
        max_recall_count=5,
        ttl_seconds=3600,
        expires_at=None,
        updated_at=None,
    )


# ---------------------------------------------------------------------------
# ContinuityService.forget_subject
# ---------------------------------------------------------------------------

class TestForgetSubject:
    def test_removes_all_markers_for_subject(self):
        svc = ContinuityService()
        svc._markers["m1"] = _make_marker("alice", "m1")
        svc._markers["m2"] = _make_marker("alice", "m2")
        svc._markers["m3"] = _make_marker("bob", "m3")  # different subject

        result = svc.forget_subject("alice")

        assert result["markers_removed"] == 2
        assert "m1" not in svc._markers
        assert "m2" not in svc._markers
        assert "m3" in svc._markers  # bob untouched

    def test_removes_scopes_for_subject(self):
        svc = ContinuityService()
        svc._scopes["alice:g1:h1:global"] = {"subject_id": "alice"}
        svc._scopes["bob:g1:h1:global"] = {"subject_id": "bob"}

        svc.forget_subject("alice")

        assert "alice:g1:h1:global" not in svc._scopes
        assert "bob:g1:h1:global" in svc._scopes

    def test_returns_zero_counts_when_no_data(self):
        svc = ContinuityService()
        result = svc.forget_subject("nonexistent")
        assert result["markers_removed"] == 0
        assert result["followups_removed"] == 0
        assert result["corrections_removed"] == 0
        assert result["scopes_removed"] == 0

    def test_does_not_touch_other_subjects_markers(self):
        svc = ContinuityService()
        svc._markers["m_alice"] = _make_marker("alice", "m_alice")
        svc._markers["m_bob"] = _make_marker("bob", "m_bob")

        svc.forget_subject("alice")

        assert "m_bob" in svc._markers
        assert svc._markers["m_bob"].subject_id == "bob"


# ---------------------------------------------------------------------------
# chronicle.retention.purge_subject_records — JSONL rewrite
# ---------------------------------------------------------------------------

class TestRewriteJsonlWithoutSubject:
    def test_removes_matching_lines(self, tmp_path: Path):
        from relic.chronicle.retention import _rewrite_jsonl_without_subject

        jsonl = tmp_path / "journal.jsonl"
        jsonl.write_text(
            json.dumps({"subject_id": "alice", "event": "a"}) + "\n"
            + json.dumps({"subject_id": "bob", "event": "b"}) + "\n"
            + json.dumps({"subject_id": "alice", "event": "c"}) + "\n",
            encoding="utf-8",
        )

        removed = _rewrite_jsonl_without_subject(jsonl, "alice")

        assert removed == 2
        remaining = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
        assert len(remaining) == 1
        assert remaining[0]["subject_id"] == "bob"

    def test_returns_zero_when_no_match(self, tmp_path: Path):
        from relic.chronicle.retention import _rewrite_jsonl_without_subject

        jsonl = tmp_path / "journal.jsonl"
        jsonl.write_text(
            json.dumps({"subject_id": "bob", "event": "b"}) + "\n",
            encoding="utf-8",
        )
        original_content = jsonl.read_text()

        removed = _rewrite_jsonl_without_subject(jsonl, "alice")

        assert removed == 0
        assert jsonl.read_text() == original_content  # file untouched

    def test_handles_malformed_lines_gracefully(self, tmp_path: Path):
        from relic.chronicle.retention import _rewrite_jsonl_without_subject

        jsonl = tmp_path / "journal.jsonl"
        jsonl.write_text(
            "not json\n"
            + json.dumps({"subject_id": "alice", "event": "x"}) + "\n",
            encoding="utf-8",
        )

        removed = _rewrite_jsonl_without_subject(jsonl, "alice")

        assert removed == 1
        lines = [l for l in jsonl.read_text().splitlines() if l.strip()]
        assert lines == ["not json"]


class TestPurgeSubjectRecords:
    def test_deletes_sqlite_rows_for_subject(self, tmp_path: Path):
        from relic.chronicle.retention import purge_subject_records

        # Build a tiny in-memory-like SQLite at tmp_path/relic.db
        db_path = tmp_path / "relic.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE chronicle_events "
            "(id TEXT PRIMARY KEY, subject_id TEXT, event_type TEXT)"
        )
        conn.execute(
            "CREATE TABLE chronicle_decisions "
            "(id TEXT PRIMARY KEY, subject_id TEXT)"
        )
        conn.execute(
            "CREATE TABLE chronicle_state_snapshots "
            "(id TEXT PRIMARY KEY, subject_id TEXT)"
        )
        conn.execute(
            "CREATE TABLE chronicle_access_log "
            "(id TEXT PRIMARY KEY, subject_id TEXT)"
        )
        conn.execute("INSERT INTO chronicle_events VALUES ('e1','alice','boot')")
        conn.execute("INSERT INTO chronicle_events VALUES ('e2','bob','boot')")
        conn.execute("INSERT INTO chronicle_decisions VALUES ('d1','alice')")
        conn.commit()
        conn.close()

        with patch("relic.chronicle.retention._get_db_connection",
                   return_value=sqlite3.connect(str(db_path))):
            result = purge_subject_records("alice", relic_home=tmp_path)

        assert result["chronicle_events_deleted"] == 1
        assert result["chronicle_decisions_deleted"] == 1

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT id FROM chronicle_events").fetchall()
        conn.close()
        assert [r[0] for r in rows] == ["e2"]  # bob survives

    def test_rewrites_journal_jsonl_files(self, tmp_path: Path):
        from relic.chronicle.retention import purge_subject_records

        journal_dir = tmp_path / "chronicle" / "journal"
        journal_dir.mkdir(parents=True)
        j = journal_dir / "2026-05-17.jsonl"
        j.write_text(
            json.dumps({"subject_id": "alice", "e": 1}) + "\n"
            + json.dumps({"subject_id": "carol", "e": 2}) + "\n",
            encoding="utf-8",
        )

        with patch("relic.chronicle.retention._get_db_connection") as mock_conn:
            mock_conn.return_value = MagicMock()
            mock_conn.return_value.execute.return_value.rowcount = 0
            purge_subject_records("alice", relic_home=tmp_path)

        remaining = [json.loads(l) for l in j.read_text().splitlines() if l.strip()]
        assert len(remaining) == 1
        assert remaining[0]["subject_id"] == "carol"


# ---------------------------------------------------------------------------
# ProfileRegistry.delete_subject
# ---------------------------------------------------------------------------

class TestDeleteSubject:
    def _write_profile(self, subject_dir: Path, subject_id: str, hermes_name: str) -> None:
        (subject_dir / "subject_profile.json").write_text(
            json.dumps({
                "subject_id": subject_id,
                "hermes_profile_name": hermes_name,
                "status": "active",
                "experiment_id": "exp1",
                "hermes_home": str(subject_dir.parent.parent / "hermes"),
                "relic_subject_home": str(subject_dir),
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }),
            encoding="utf-8",
        )

    def test_removes_subject_directory(self, tmp_path: Path):
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry(relic_home=tmp_path)
        subject_dir = registry._subject_dir("alice")
        subject_dir.mkdir(parents=True)
        self._write_profile(subject_dir, "alice", "alice_gumi")
        (subject_dir / "relic.db").write_bytes(b"fake db")

        result = registry.delete_subject("alice")

        assert not subject_dir.exists()
        assert result["subject_id"] == "alice"
        assert result["hermes_profile_name"] == "alice_gumi"
        assert str(subject_dir) in result["deleted_paths"]

    def test_returns_empty_when_subject_not_found(self, tmp_path: Path):
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry(relic_home=tmp_path)
        result = registry.delete_subject("nonexistent")

        assert result["deleted_paths"] == []
        assert result["hermes_profile_name"] is None

    def test_does_not_delete_other_subjects(self, tmp_path: Path):
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry(relic_home=tmp_path)
        for sid in ("alice", "bob"):
            d = registry._subject_dir(sid)
            d.mkdir(parents=True)
            self._write_profile(d, sid, f"{sid}_gumi")

        registry.delete_subject("alice")

        assert not registry._subject_dir("alice").exists()
        assert registry._subject_dir("bob").exists()


# ---------------------------------------------------------------------------
# CLI: relic subject forget — confirmation guard
# ---------------------------------------------------------------------------

class TestSubjectForgetCLI:
    def test_aborts_on_wrong_confirmation(self, tmp_path: Path, capsys):
        from relic.cli import _subject_forget

        with patch("relic.cli.ProfileRegistry") as mock_reg_cls:
            mock_reg_cls.return_value.get_subject.return_value = None
            with patch("builtins.input", return_value="wrong-id"):
                rc = _subject_forget("alice", skip_confirm=False)

        assert rc == 1
        captured = capsys.readouterr()
        assert "Mismatch" in captured.out or "Aborted" in captured.out

    def test_aborts_on_keyboard_interrupt(self, tmp_path: Path):
        from relic.cli import _subject_forget

        with patch("relic.cli.ProfileRegistry") as mock_reg_cls:
            mock_reg_cls.return_value.get_subject.return_value = None
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                rc = _subject_forget("alice", skip_confirm=False)

        assert rc == 1

    def test_skip_confirm_deletes_without_prompt(self, tmp_path: Path):
        from relic.cli import _subject_forget

        with patch("relic.cli.ProfileRegistry") as mock_reg_cls, \
             patch("relic.cli.purge_subject_records", return_value={}, create=True), \
             patch("relic.shared_continuity.service.ContinuityService.forget_subject"):
            mock_registry = MagicMock()
            mock_registry.get_subject.return_value = None
            mock_registry.delete_subject.return_value = {
                "deleted_paths": [],
                "hermes_profile_name": None,
            }
            mock_reg_cls.return_value = mock_registry

            with patch("relic.chronicle.retention.purge_subject_records", return_value={}):
                with patch("builtins.input", side_effect=AssertionError("input must not be called")):
                    rc = _subject_forget("alice", skip_confirm=True)

        assert rc == 0

    def test_confirmation_matches_subject_id_proceeds(self, tmp_path: Path):
        from relic.cli import _subject_forget

        with patch("relic.cli.ProfileRegistry") as mock_reg_cls, \
             patch("relic.chronicle.retention.purge_subject_records", return_value={}), \
             patch("relic.shared_continuity.service.ContinuityService.forget_subject"):
            mock_registry = MagicMock()
            mock_registry.get_subject.return_value = None
            mock_registry.delete_subject.return_value = {
                "deleted_paths": [],
                "hermes_profile_name": None,
            }
            mock_reg_cls.return_value = mock_registry

            with patch("builtins.input", return_value="alice"):
                rc = _subject_forget("alice", skip_confirm=False)

        assert rc == 0
