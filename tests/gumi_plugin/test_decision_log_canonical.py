"""Tests for canonical decision log: decision_type plumbing + RELIC_HOME path."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from relic.gumi_plugin.cron_wiring import (
    emit_decision_event,
    make_decision,
    render_no_agent_script,
)
from relic.hermes_runtime import (
    DecisionEvent,
    RuntimeDecision,
    RuntimeDecisionReason,
)


def test_make_decision_accepts_decision_type(monkeypatch):
    calls = {}

    def fake_eval(subject_id, gumi_instance_id, hermes_profile_id, decision_type="checkin"):
        calls["decision_type"] = decision_type
        return RuntimeDecision.NO_REPLY, [], None

    monkeypatch.setattr("relic.gumi_plugin.cron_wiring._evaluate_decision", fake_eval)

    make_decision("s1", "g1", "p1", decision_type="proactivity")

    assert calls["decision_type"] == "proactivity"


def test_rendered_script_passes_decision_type_from_filename(tmp_path: Path):
    script = render_no_agent_script(tmp_path / "relic_followup_decision.sh")
    assert "DECISION_TYPE=" in script
    assert "make_decision(" in script
    assert "decision_type=decision_type" in script


def test_rendered_script_embeds_distinct_defaults_per_dtype(tmp_path: Path):
    checkin = render_no_agent_script(tmp_path / "relic_checkin_decision.sh")
    followup = render_no_agent_script(tmp_path / "relic_followup_decision.sh")
    proactivity = render_no_agent_script(tmp_path / "relic_proactivity_decision.sh")
    diegetic = render_no_agent_script(tmp_path / "relic_diegetic_decision.sh")

    # Each script must embed its own dtype default (either via interpolated literal
    # or basename($0) derivation). All rendered contents must differ.
    assert checkin != followup
    assert followup != proactivity
    assert checkin != proactivity
    assert diegetic != checkin
    assert diegetic != followup
    assert diegetic != proactivity

    # Spot-check that the expected default token appears somewhere.
    assert "checkin" in checkin
    assert "followup" in followup
    assert "proactivity" in proactivity
    assert "diegetic" in diegetic


def test_rendered_script_defaults_to_diegetic_for_diegetic_job_name(tmp_path: Path):
    script = render_no_agent_script(tmp_path / "relic_diegetic_decision.sh")
    assert "# Decision type default: diegetic" in script
    assert 'DECISION_TYPE="${RELIC_DECISION_TYPE:-diegetic}"' in script


def test_rendered_script_defaults_to_proactivity_for_proactive_job_name(tmp_path: Path):
    script = render_no_agent_script(tmp_path / "relic_proactive_decision.sh")
    assert "# Decision type default: proactivity" in script
    assert 'DECISION_TYPE="${RELIC_DECISION_TYPE:-proactivity}"' in script


def test_decision_event_round_trip_preserves_optional_fields():
    event = DecisionEvent(
        decision=RuntimeDecision.DELIVER,
        reason_codes=[RuntimeDecisionReason.no_due_work],
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="p1",
        decision_type="followup",
        event_kind="checkin",
        posture="observe",
        features_id=42,
        non_response_streak=2,
        followup_non_response_streak=1,
        reach_score=0.49,
        response_deadline_at="2026-05-19T12:00:00+00:00",
        cadence_decay_applied=False,
        outcome_status="delivered",
        wake_agent_emitted=True,
        message_hash="abc123",
        delivered=True,
    )
    payload = event.to_dict()
    assert payload["decision_type"] == "followup"
    assert payload["event_kind"] == "checkin"
    assert payload["posture"] == "observe"
    assert payload["features_id"] == 42
    assert payload["non_response_streak"] == 2
    assert payload["followup_non_response_streak"] == 1
    assert payload["reach_score"] == pytest.approx(0.49)
    assert payload["response_deadline_at"] == "2026-05-19T12:00:00+00:00"
    assert payload["cadence_decay_applied"] is False
    assert payload["outcome_status"] == "delivered"
    assert payload["wake_agent_emitted"] is True
    assert payload["message_hash"] == "abc123"
    assert payload["delivered"] is True

    restored = DecisionEvent.from_dict(payload)
    assert restored.decision_type == event.decision_type
    assert restored.event_kind == event.event_kind
    assert restored.posture == event.posture
    assert restored.features_id == event.features_id
    assert restored.non_response_streak == event.non_response_streak
    assert restored.followup_non_response_streak == event.followup_non_response_streak
    assert restored.reach_score == pytest.approx(event.reach_score)
    assert restored.outcome_status == event.outcome_status
    assert restored.wake_agent_emitted == event.wake_agent_emitted


def test_decision_event_from_dict_tolerates_missing_optional_fields():
    legacy = {
        "decision": "NO_REPLY",
        "reason_codes": ["followup_not_due"],
        "subject_id": "s1",
        "gumi_instance_id": "g1",
        "hermes_profile_id": "p1",
        "target_id": None,
        "metadata": {"source": "no_agent_cron"},
        "created_at": "2026-05-19T00:00:00+00:00",
    }
    restored = DecisionEvent.from_dict(legacy)
    assert restored.decision_type is None
    assert restored.posture is None
    assert restored.features_id is None
    assert restored.outcome_status is None


def test_emit_decision_event_uses_relic_home_path(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_HOME", str(tmp_path))
    emit_decision_event(
        decision=RuntimeDecision.NO_REPLY,
        reason_codes=[RuntimeDecisionReason.followup_not_due],
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="p1",
        decision_type="checkin",
    )
    log_path = tmp_path / "decision_events.jsonl"
    assert log_path.exists(), f"writer must use RELIC_HOME (expected {log_path})"
    line = log_path.read_text().splitlines()[-1]
    record = json.loads(line)
    assert record["decision"] == "NO_REPLY"
    assert record["decision_type"] == "checkin"


def test_emit_decision_event_writes_outcome_status_and_event_kind(tmp_path, monkeypatch):
    """Reviewer fix: outcome_status='delivered' + event_kind/posture must land
    in the canonical event so the reconciler and metrics can find them."""
    monkeypatch.setenv("RELIC_HOME", str(tmp_path))
    emit_decision_event(
        decision=RuntimeDecision.DELIVER,
        reason_codes=[RuntimeDecisionReason.no_due_work],
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="p1",
        decision_type="checkin",
        event_kind="checkin",
        posture="observe",
        outcome_status="delivered",
        delivered=True,
        wake_agent_emitted=True,
    )
    log_path = tmp_path / "decision_events.jsonl"
    record = json.loads(log_path.read_text().splitlines()[-1])
    assert record["outcome_status"] == "delivered"
    assert record["event_kind"] == "checkin"
    assert record["posture"] == "observe"
    assert record["delivered"] is True
    assert record["wake_agent_emitted"] is True
