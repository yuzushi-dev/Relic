"""Tests for cron_wiring.make_decision → naturalness policy wiring (Plan §Task 7)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from relic.gumi_plugin.cron_wiring import make_decision
from relic.hermes_runtime import RuntimeDecision


def test_policy_disabled_preserves_current_deliver_shape(monkeypatch):
    monkeypatch.delenv("RELIC_CHECKIN_POLICY_ENABLED", raising=False)
    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock:
        eval_mock.return_value = (
            RuntimeDecision.DELIVER,
            [],
            {"message": "DELIVER\ntipo: text"},
        )
        decision, _, data = make_decision("s1", "g1", "p1", decision_type="checkin")
    assert decision == RuntimeDecision.DELIVER
    assert data is not None
    assert data["message"].startswith("DELIVER")
    assert "event_type" not in data
    assert "posture" not in data


def test_policy_enabled_silent_returns_no_reply(monkeypatch):
    monkeypatch.setenv("RELIC_CHECKIN_POLICY_ENABLED", "1")
    from relic.checkin.policy import Decision, EventType, Posture

    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock, \
         patch("relic.gumi_plugin.cron_wiring._run_outcome_reconciler"):
        eval_mock.return_value = (
            RuntimeDecision.DELIVER,
            [],
            {"message": "DELIVER\ntipo: text"},
        )
        with patch(
            "relic.checkin.policy.select_decision",
            return_value=Decision(EventType.SILENT, Posture.QUIET, "test"),
        ):
            decision, _, data = make_decision("s1", "g1", "p1", decision_type="checkin")
    assert decision == RuntimeDecision.NO_REPLY
    assert data is None


def test_policy_enabled_non_silent_prepends_constraint_header(monkeypatch):
    monkeypatch.setenv("RELIC_CHECKIN_POLICY_ENABLED", "1")
    from relic.checkin.policy import Decision, EventType, Posture

    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock, \
         patch("relic.gumi_plugin.cron_wiring._run_outcome_reconciler"):
        eval_mock.return_value = (
            RuntimeDecision.DELIVER,
            [],
            {"message": "DELIVER\ntipo: text"},
        )
        with patch(
            "relic.checkin.policy.select_decision",
            return_value=Decision(EventType.CHECKIN, Posture.OBSERVE, "default_observe"),
        ):
            decision, _, data = make_decision("s1", "g1", "p1", decision_type="checkin")
    assert decision == RuntimeDecision.DELIVER
    assert data is not None
    assert data["event_type"] == "checkin"
    assert data["posture"] == "observe"
    assert "[EVENTO: checkin]" in data["message"]
    assert data["message"].rstrip().endswith("DELIVER\ntipo: text")
