"""Chronicle access audit tests, T023 log_access + log_query/export/delete."""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path


def _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir):
    from relic.chronicle import emitter as em

    def _fake_conn():
        return sqlite3.connect(tmp_relic_db)

    monkeypatch.setattr(em, "_get_db_connection", _fake_conn)
    monkeypatch.setattr(em, "_chronicle_base_dir", lambda: Path(tmp_chronicle_dir))


class TestLogAccess:
    def test_log_access_returns_uuid(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import log_access

        aid = log_access(
            accessor_id="researcher:test",
            access_kind="query",
            target_filter={"subject_id": "x"},
            rows_returned=42,
        )
        assert isinstance(aid, uuid.UUID)
        assert aid.int != 0

    def test_log_access_persists_to_db(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import log_access

        aid = log_access(
            accessor_id="researcher:cristina",
            access_kind="export",
            target_filter={"subject_id": "subj_x"},
            rows_returned=1234,
        )
        conn = sqlite3.connect(tmp_relic_db)
        row = conn.execute(
            "SELECT accessor_id, access_kind, rows_returned FROM chronicle_access_log WHERE access_id = ?",
            (str(aid),),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "researcher:cristina"
        assert row[1] == "export"
        assert row[2] == 1234

    def test_log_access_invalid_kind_falls_back_to_query(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import log_access

        aid = log_access(
            accessor_id="x",
            access_kind="not_a_real_kind",
        )
        conn = sqlite3.connect(tmp_relic_db)
        row = conn.execute(
            "SELECT access_kind FROM chronicle_access_log WHERE access_id = ?",
            (str(aid),),
        ).fetchone()
        conn.close()
        assert row[0] == "query"  # safe fallback

    def test_result_hash_computed_when_data_present(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import log_access

        aid = log_access(
            accessor_id="x",
            access_kind="query",
            result_data={"rows": [1, 2, 3]},
        )
        conn = sqlite3.connect(tmp_relic_db)
        rh = conn.execute(
            "SELECT result_hash FROM chronicle_access_log WHERE access_id = ?",
            (str(aid),),
        ).fetchone()[0]
        conn.close()
        assert rh is not None
        assert len(rh) == 32  # 32-char truncated sha256

    def test_result_hash_deterministic(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import log_access

        data = {"rows": [1, 2, 3], "meta": "x"}
        aid1 = log_access(accessor_id="a", access_kind="query", result_data=data)
        aid2 = log_access(accessor_id="b", access_kind="query", result_data=data)

        conn = sqlite3.connect(tmp_relic_db)
        rh1 = conn.execute("SELECT result_hash FROM chronicle_access_log WHERE access_id = ?", (str(aid1),)).fetchone()[0]
        rh2 = conn.execute("SELECT result_hash FROM chronicle_access_log WHERE access_id = ?", (str(aid2),)).fetchone()[0]
        conn.close()
        assert rh1 == rh2


class TestConvenienceWrappers:
    def test_log_query(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import log_query

        aid = log_query(accessor_id="x", filters={"event_type": "model"}, rows_returned=5)
        conn = sqlite3.connect(tmp_relic_db)
        kind = conn.execute(
            "SELECT access_kind FROM chronicle_access_log WHERE access_id = ?", (str(aid),)
        ).fetchone()[0]
        conn.close()
        assert kind == "query"

    def test_log_export(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import log_export

        aid = log_export(accessor_id="x", subject_id="s", bytes_written=1000)
        conn = sqlite3.connect(tmp_relic_db)
        kind = conn.execute(
            "SELECT access_kind FROM chronicle_access_log WHERE access_id = ?", (str(aid),)
        ).fetchone()[0]
        conn.close()
        assert kind == "export"

    def test_log_delete(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import log_delete

        aid = log_delete(accessor_id="x", subject_id="s", rows_deleted=42, cascade=True)
        conn = sqlite3.connect(tmp_relic_db)
        kind = conn.execute(
            "SELECT access_kind FROM chronicle_access_log WHERE access_id = ?", (str(aid),)
        ).fetchone()[0]
        conn.close()
        assert kind == "delete"
