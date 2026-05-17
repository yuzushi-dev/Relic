"""Chronicle acceptance tests — definition of done per research.md §16.

Each test maps to one acceptance question. They use the underlying reader/
emitter API rather than the CLI (CLI scaffold T071+ comes later), but exercise
the same data path the CLI will hit.

Pass criteria: every question is answerable from the trace store with one
documented query.
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest


def _patch_all(monkeypatch, tmp_relic_db, tmp_chronicle_dir):
    from relic.chronicle import emitter as em
    from relic.chronicle import reader as rd
    from relic.chronicle import retention as rt
    from relic.chronicle import provenance as pv

    def _fake_conn():
        return sqlite3.connect(tmp_relic_db)

    monkeypatch.setattr(em, "_get_db_connection", _fake_conn)
    monkeypatch.setattr(em, "_chronicle_base_dir", lambda: Path(tmp_chronicle_dir))
    monkeypatch.setattr(rd, "_get_db_connection", _fake_conn)
    monkeypatch.setattr(rt, "_get_db_connection", _fake_conn)
    monkeypatch.setattr(pv, "_get_db_connection", _fake_conn)


@pytest.fixture
def seeded_trace(monkeypatch, tmp_relic_db, tmp_chronicle_dir):
    """Seed a complete cron→model→memory→delivery trace for acceptance queries."""
    _patch_all(monkeypatch, tmp_relic_db, tmp_chronicle_dir)
    from relic.chronicle import (
        emit_event, emit_decision, emit_snapshot, add_edge,
        EventCategory,
    )

    tid = uuid.uuid4()
    sid = uuid.uuid4()
    subj = "test_subj"

    # Q1: session events
    msg_in = emit_event(
        event_type="message_received",
        event_category=EventCategory.MESSAGE,
        source_module="relic.hermes_runtime",
        trace_id=tid, session_id=sid, subject_id=subj,
        agent_id="hermes",
        payload={"platform": "telegram", "content_hash": "sha256:abc123"},
    )

    # Q3-5: model call
    mc = emit_event(
        event_type="model_called",
        event_category=EventCategory.MODEL,
        source_module="relic.gumi.llm_narrator",
        trace_id=tid, session_id=sid, subject_id=subj,
        agent_id="gumi", parent_event_id=msg_in,
        payload={
            "model_id": "qwen3.5-plus",
            "prompt_hash": "sha256:promptdeadbeef0123",
            "params": {"temperature": 0.7},
        },
    )
    mr = emit_event(
        event_type="model_returned",
        event_category=EventCategory.MODEL,
        source_module="relic.gumi.llm_narrator",
        trace_id=tid, session_id=sid, subject_id=subj,
        agent_id="gumi", parent_event_id=mc,
        payload={
            "response_hash": "sha256:responsefeedface01",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
    )

    # Q6-7: tool call
    tc = emit_event(
        event_type="tool_called",
        event_category=EventCategory.TOOL,
        source_module="relic.hermes_plugin.commands",
        trace_id=tid, session_id=sid, subject_id=subj,
        payload={"tool_name": "search_memory", "args_hash": "sha256:argshashdeadbeef"},
    )
    emit_event(
        event_type="tool_returned",
        event_category=EventCategory.TOOL,
        source_module="relic.hermes_plugin.commands",
        trace_id=tid, session_id=sid, subject_id=subj,
        parent_event_id=tc,
        payload={"outcome": "success", "result_hash": "sha256:toolresult0123abcd"},
    )

    # Q8-9: memory
    emit_event(
        event_type="memory_read",
        event_category=EventCategory.MEMORY,
        source_module="relic.hermes_plugin.memory_provider",
        trace_id=tid, session_id=sid, subject_id=subj,
        payload={"namespace": "gumi-test", "markers_returned": 3},
    )
    emit_event(
        event_type="memory_write",
        event_category=EventCategory.MEMORY,
        source_module="relic.hermes_plugin.memory_provider",
        trace_id=tid, session_id=sid, subject_id=subj,
        payload={"namespace": "gumi-test", "marker_hash": "sha256:markerhashabcdef01"},
    )

    # Q10-12: profile read/write + snapshot diff
    emit_event(
        event_type="profile_read",
        event_category=EventCategory.PROFILE,
        source_module="relic.profile.registry",
        trace_id=tid, session_id=sid, subject_id=subj,
        profile_id="gumi-test",
        payload={"profile_id": "gumi-test"},
    )
    snap_before = emit_snapshot(
        snapshot_type="hermes_profile",
        subject_id=subj,
        scope_ref="gumi-test",
        content={"version": 1, "tone": "neutral"},
        trace_id=tid,
    )
    pw = emit_event(
        event_type="profile_write_applied",
        event_category=EventCategory.PROFILE,
        source_module="relic.profile.registry",
        trace_id=tid, session_id=sid, subject_id=subj,
        profile_id="gumi-test",
        payload={"field_path": "tone", "previous_value_hash": "sha256:beforehashabc012345"},
    )
    snap_after = emit_snapshot(
        snapshot_type="hermes_profile",
        subject_id=subj,
        scope_ref="gumi-test",
        content={"version": 2, "tone": "warm"},
        trace_id=tid,
        previous_snapshot_id=snap_before,
    )

    # Q13-14: decision + evidence
    dec = emit_decision(
        decision_kind="tone_selection",
        selected_action={"tone": "warm"},
        actor_type="agent",
        actor_id="gumi",
        observable_inputs={"signal": "warmth"},
        evidence_refs=[str(mr), str(snap_before)],
        rationale_summary="Subject signaled need for warmth.",
        trace_id=tid,
        session_id=sid,
        subject_id=subj,
    )

    # Q15-16: error + retry
    err = emit_event(
        event_type="error_raised",
        event_category=EventCategory.ERROR,
        source_module="relic.gumi.llm_narrator",
        trace_id=tid, session_id=sid, subject_id=subj,
        severity="error",
        error_code="TIMEOUT",
        payload={"error_class": "TimeoutError"},
    )
    emit_event(
        event_type="retry_started",
        event_category=EventCategory.ERROR,
        source_module="relic.gumi.llm_narrator",
        trace_id=tid, session_id=sid, subject_id=subj,
        parent_event_id=err,
        retry_count=1,
        payload={"strategy": "backoff"},
    )

    # Q17-18: artifact + provenance
    artifact_id = uuid.uuid4()
    emit_event(
        event_type="artifact_registered",
        event_category=EventCategory.ARTIFACT,
        source_module="relic.artifacts.registry",
        trace_id=tid, session_id=sid, subject_id=subj,
        payload={"artifact_id": str(artifact_id), "artifact_type": "runtime_profile"},
    )
    add_edge(
        artifact_id=artifact_id,
        from_node_type="event",
        from_node_id=mr,
        relation="wasGeneratedBy",
        trace_id=tid,
    )

    # Q19-20: sensitive event with consent_basis
    from relic.persistence import PrivacyLevel
    emit_event(
        event_type="privacy_decision",
        event_category=EventCategory.PRIVACY,
        source_module="relic.privacy.gateway",
        trace_id=tid, session_id=sid, subject_id=subj,
        sensitivity=PrivacyLevel.S1_QUARANTINE,
        consent_basis="PRIVACY",  # legitimate interest
        severity="warning",
        payload={"stage": "input_scan", "privacy_level_assigned": "s1"},
    )

    return {
        "trace_id": tid,
        "session_id": sid,
        "subject_id": subj,
        "model_call_id": mc,
        "model_return_id": mr,
        "tool_call_id": tc,
        "snapshot_before_id": snap_before,
        "snapshot_after_id": snap_after,
        "decision_id": dec,
        "artifact_id": artifact_id,
        "error_id": err,
    }


# ===========================================================================
# Acceptance tests — 23 questions
# ===========================================================================

class TestAcceptance:
    # Q1
    def test_q01_what_happened_in_session(self, seeded_trace):
        from relic.chronicle import query_events
        sid = seeded_trace["session_id"]
        rows = query_events(session_id=sid, limit=100)
        assert len(rows) >= 8

    # Q2
    def test_q02_which_agent_acted(self, seeded_trace):
        from relic.chronicle import query_events
        tid = seeded_trace["trace_id"]
        rows = query_events(trace_id=tid, limit=100)
        agents = {r["agent_id"] for r in rows if r.get("agent_id")}
        assert "hermes" in agents
        assert "gumi" in agents

    # Q3
    def test_q03_which_model_called(self, seeded_trace):
        import json
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="model_called")
        assert len(rows) == 1
        payload = json.loads(rows[0]["payload"])
        assert payload["model_id"] == "qwen3.5-plus"

    # Q4
    def test_q04_prompt_hash_present(self, seeded_trace):
        import json
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="model_called")
        payload = json.loads(rows[0]["payload"])
        assert payload["prompt_hash"].startswith("sha256:")

    # Q5
    def test_q05_response_hash_present(self, seeded_trace):
        import json
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="model_returned")
        payload = json.loads(rows[0]["payload"])
        assert payload["response_hash"].startswith("sha256:")

    # Q6
    def test_q06_which_tool_called(self, seeded_trace):
        import json
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="tool_called")
        assert len(rows) == 1
        payload = json.loads(rows[0]["payload"])
        assert payload["tool_name"] == "search_memory"
        assert payload["args_hash"].startswith("sha256:")

    # Q7
    def test_q07_tool_result(self, seeded_trace):
        import json
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="tool_returned")
        payload = json.loads(rows[0]["payload"])
        assert payload["outcome"] == "success"
        assert payload["result_hash"].startswith("sha256:")

    # Q8
    def test_q08_memory_reads(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="memory_read")
        assert len(rows) == 1

    # Q9
    def test_q09_memory_writes(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="memory_write")
        assert len(rows) == 1

    # Q10
    def test_q10_which_profile_read(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="profile_read")
        assert len(rows) == 1
        assert rows[0]["profile_id"] == "gumi-test"

    # Q11
    def test_q11_which_profile_modified(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="profile_write_applied")
        assert len(rows) == 1
        assert rows[0]["profile_id"] == "gumi-test"

    # Q12
    def test_q12_profile_diff_via_snapshots(self, seeded_trace):
        from relic.chronicle import query_snapshots
        rows = query_snapshots(subject_id=seeded_trace["subject_id"], snapshot_type="hermes_profile")
        assert len(rows) == 2
        # Latest snapshot links back to previous
        latest = max(rows, key=lambda r: r["captured_at"])
        assert latest["previous_snapshot_id"] == str(seeded_trace["snapshot_before_id"])

    # Q13
    def test_q13_decision_records(self, seeded_trace):
        from relic.chronicle import query_decisions
        rows = query_decisions(trace_id=seeded_trace["trace_id"])
        assert len(rows) == 1
        assert rows[0]["decision_kind"] == "tone_selection"

    # Q14
    def test_q14_decision_evidence(self, seeded_trace):
        import json
        from relic.chronicle import query_decisions
        rows = query_decisions(trace_id=seeded_trace["trace_id"])
        evidence = json.loads(rows[0]["evidence_refs"])
        assert str(seeded_trace["model_return_id"]) in evidence
        assert str(seeded_trace["snapshot_before_id"]) in evidence

    # Q15
    def test_q15_errors(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="error_raised")
        assert len(rows) == 1
        assert rows[0]["error_code"] == "TIMEOUT"

    # Q16
    def test_q16_retries(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="retry_started")
        assert len(rows) == 1
        assert rows[0]["parent_event_id"] == str(seeded_trace["error_id"])
        assert rows[0]["retry_count"] == 1

    # Q17
    def test_q17_artifacts_generated(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], event_type="artifact_registered")
        assert len(rows) == 1

    # Q18
    def test_q18_provenance_subgraph(self, seeded_trace):
        from relic.chronicle import get_ancestors
        ancestors = get_ancestors(seeded_trace["artifact_id"], depth=2)
        assert len(ancestors) >= 1
        assert any(a["from_node_id"] == str(seeded_trace["model_return_id"]) for a in ancestors)

    # Q19
    def test_q19_sensitive_data_filterable(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"], sensitivity="s1")
        assert len(rows) >= 1
        assert all(r["sensitivity"] == "s1" for r in rows)

    # Q20
    def test_q20_consent_basis_present(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"])
        bases = {r["consent_basis"] for r in rows if r.get("consent_basis")}
        assert "PRIVACY" in bases

    # Q21 — exportable count (no CLI, just count of subject events)
    def test_q21_exportable_count(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(subject_id=seeded_trace["subject_id"], limit=1000)
        assert len(rows) >= 8  # everything we seeded for this subject

    # Q22 — deletable count via reaper dry-run
    def test_q22_deletable_dry_run(self, monkeypatch, tmp_relic_db, tmp_chronicle_dir, seeded_trace):
        from relic.chronicle import reaper_run
        result = reaper_run(dry_run=True, subject_id=seeded_trace["subject_id"])
        assert "total_deleted" in result
        assert result["dry_run"] is True

    # Q23 — retention candidates per policy
    def test_q23_retention_policy_counts(self, seeded_trace):
        from relic.chronicle import query_events
        rows = query_events(trace_id=seeded_trace["trace_id"])
        policies = {r["retention_policy"] for r in rows}
        assert "standard_365d" in policies
