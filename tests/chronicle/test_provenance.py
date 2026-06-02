"""Chronicle provenance tests, T021 graph add/get/verify."""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path


def _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir):
    from relic.chronicle import emitter as em
    from relic.chronicle import provenance as pv

    def _fake_conn():
        return sqlite3.connect(tmp_relic_db)

    monkeypatch.setattr(em, "_get_db_connection", _fake_conn)
    monkeypatch.setattr(em, "_chronicle_base_dir", lambda: Path(tmp_chronicle_dir))
    monkeypatch.setattr(pv, "_get_db_connection", _fake_conn)


class TestAddEdge:
    def test_add_edge_returns_uuid(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import add_edge

        eid = add_edge(
            artifact_id=uuid.uuid4(),
            from_node_type="event",
            from_node_id=uuid.uuid4(),
            relation="used",
        )
        assert isinstance(eid, uuid.UUID)
        assert eid.int != 0

    def test_add_edge_persists_to_db(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import add_edge

        aid = uuid.uuid4()
        add_edge(
            artifact_id=aid,
            from_node_type="event",
            from_node_id=uuid.uuid4(),
            relation="wasGeneratedBy",
        )
        conn = sqlite3.connect(tmp_relic_db)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM chronicle_provenance_edges WHERE artifact_id = ?",
            (str(aid),),
        ).fetchone()[0]
        conn.close()
        assert cnt == 1


class TestAncestorsDescendants:
    def test_get_ancestors_returns_edges(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import add_edge, get_ancestors

        artifact = uuid.uuid4()
        source_event = uuid.uuid4()
        add_edge(
            artifact_id=artifact,
            from_node_type="event",
            from_node_id=source_event,
            relation="used",
        )

        ancestors = get_ancestors(artifact, depth=2)
        assert len(ancestors) >= 1
        assert any(a["from_node_id"] == str(source_event) for a in ancestors)

    def test_get_descendants_follows_artifact_chain(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import add_edge, get_descendants

        parent = uuid.uuid4()
        child = uuid.uuid4()
        # edge: child wasDerivedFrom parent (so child has parent as from_node)
        add_edge(
            artifact_id=child,
            from_node_type="artifact",
            from_node_id=parent,
            relation="wasDerivedFrom",
        )

        descendants = get_descendants(parent, depth=2)
        assert len(descendants) >= 1
        assert any(d["artifact_id"] == str(child) for d in descendants)

    def test_get_ancestors_depth_zero_returns_empty(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir):
        _patch(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
        from relic.chronicle import get_ancestors

        assert get_ancestors(uuid.uuid4(), depth=0) == []
