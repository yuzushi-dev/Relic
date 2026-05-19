"""Tests for the proactive queue consumer (Plan §Task 9)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relic.gumi_plugin.proactive_consumer import (
    _queue_path,
    consume_one,
    load_candidates,
    save_candidates,
)
from relic.hermes_runtime import RuntimeDecision
from relic.shared_continuity.service import enqueue_proactive_candidate


def test_expired_candidate_is_skipped(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RELIC_HOME", str(tmp_path))
    enqueue_proactive_candidate(
        subject_id="s1",
        signal_ref="memory.md#L42",
        suggested_posture="brief_share",
        priority=0.8,
        expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    )
    decision, _, data = consume_one(
        "s1",
        hermes_home=tmp_path / "hermes",
        relic_home=tmp_path,
    )
    assert decision == RuntimeDecision.NO_REPLY
    assert data is None


def test_low_priority_candidate_returns_no_delivery(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RELIC_HOME", str(tmp_path))
    enqueue_proactive_candidate(
        subject_id="s1",
        signal_ref="memory.md#L42",
        priority=0.2,
    )
    decision, _, data = consume_one(
        "s1",
        hermes_home=tmp_path / "hermes",
        relic_home=tmp_path,
    )
    assert decision == RuntimeDecision.NO_REPLY
    assert data is None


def test_high_salience_candidate_returns_deliver(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RELIC_HOME", str(tmp_path))
    enqueue_proactive_candidate(
        subject_id="s1",
        signal_ref="memory.md#L42",
        priority=0.9,
        suggested_posture="brief_share",
    )
    decision, _, data = consume_one(
        "s1",
        hermes_home=tmp_path / "hermes",
        relic_home=tmp_path,
    )
    assert decision == RuntimeDecision.DELIVER
    assert data is not None
    assert data["decision_type"] == "proactivity"
    assert data["proactive_signal_ref"] == "memory.md#L42"
    assert data["suggested_posture"] == "brief_share"


def test_queue_is_rewritten_without_expired_entries(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RELIC_HOME", str(tmp_path))
    enqueue_proactive_candidate(
        subject_id="s1",
        signal_ref="ref-1",
        priority=0.9,
        expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    )
    enqueue_proactive_candidate(
        subject_id="s1",
        signal_ref="ref-2",
        priority=0.9,
    )
    consume_one("s1", hermes_home=tmp_path / "hermes", relic_home=tmp_path)

    path = _queue_path("s1", tmp_path)
    rows = load_candidates(path)
    # expired ref-1 dropped, ref-2 consumed and tagged.
    signals = [r.get("signal_ref") for r in rows]
    assert "ref-1" not in signals
    assert "ref-2" in signals
    consumed_rows = [r for r in rows if r.get("consumed_at")]
    assert len(consumed_rows) == 1


def test_enqueue_dedupe_key_returns_existing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RELIC_HOME", str(tmp_path))
    first = enqueue_proactive_candidate(
        subject_id="s1",
        signal_ref="ref-1",
        priority=0.8,
        dedupe_key="event-abc",
    )
    second = enqueue_proactive_candidate(
        subject_id="s1",
        signal_ref="ref-1",
        priority=0.8,
        dedupe_key="event-abc",
    )
    assert first["id"] == second["id"]


def test_provision_for_subject_omits_proactivity_when_queue_enabled(
    tmp_path: Path, monkeypatch
):
    from relic.gumi_plugin.cron_wiring import provision_for_subject

    monkeypatch.setenv("RELIC_PROACTIVE_QUEUE_ENABLED", "1")
    result = provision_for_subject(
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="p1",
        dry_run=True,
        hermes_home=str(tmp_path / "hermes"),
    )
    assert "proactivity" not in result["scripts"]
    # checkin + followup + memory_sync still provisioned.
    assert "checkin" in result["scripts"]
    assert "followup" in result["scripts"]


def test_provision_for_subject_keeps_proactivity_by_default(
    tmp_path: Path, monkeypatch
):
    from relic.gumi_plugin.cron_wiring import provision_for_subject

    monkeypatch.delenv("RELIC_PROACTIVE_QUEUE_ENABLED", raising=False)
    result = provision_for_subject(
        subject_id="s2",
        gumi_instance_id="g1",
        hermes_profile_id="p1",
        dry_run=True,
        hermes_home=str(tmp_path / "hermes"),
    )
    assert "proactivity" in result["scripts"]
