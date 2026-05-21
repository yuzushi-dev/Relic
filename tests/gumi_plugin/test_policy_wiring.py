"""Tests for cron_wiring.make_decision → naturalness policy wiring (Plan §Task 7)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from relic.checkin.policy import CheckinFeatures
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


def test_policy_enabled_diegetic_candidate_returns_no_reply_when_silent(monkeypatch):
    monkeypatch.setenv("RELIC_CHECKIN_POLICY_ENABLED", "1")

    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock, \
         patch("relic.gumi_plugin.cron_wiring._run_outcome_reconciler"):
        eval_mock.return_value = (
            RuntimeDecision.CANDIDATE,
            [],
            {"message": "CANDIDATE\ntipo: text"},
        )
        with patch(
            "relic.checkin.features.build_checkin_features",
            return_value=CheckinFeatures(
                subject_id="s1",
                diegetic_enabled=False,
                diegetic_tolerance=0.9,
            ),
        ) as features_mock:
            decision, _, data = make_decision("s1", "g1", "p1", decision_type="diegetic")

    assert features_mock.call_args.kwargs["decision_type"] == "diegetic"
    assert decision == RuntimeDecision.NO_REPLY
    assert data is None


def test_policy_enabled_diegetic_candidate_honors_non_silent_decision(monkeypatch):
    monkeypatch.setenv("RELIC_CHECKIN_POLICY_ENABLED", "1")

    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock, \
         patch("relic.gumi_plugin.cron_wiring._run_outcome_reconciler"):
        eval_mock.return_value = (
            RuntimeDecision.CANDIDATE,
            [],
            {"message": "CANDIDATE\ntipo: text"},
        )
        with patch(
            "relic.checkin.features.build_checkin_features",
            return_value=CheckinFeatures(
                subject_id="s1",
                diegetic_enabled=True,
                diegetic_tolerance=0.7,
            ),
        ) as features_mock:
            decision, _, data = make_decision("s1", "g1", "p1", decision_type="diegetic")

    assert features_mock.call_args.kwargs["decision_type"] == "diegetic"
    assert decision == RuntimeDecision.CANDIDATE
    assert data is not None
    assert data["event_type"] == "diegetic"
    assert data["posture"] == "small_share"
    assert "[EVENTO: diegetic]" in data["message"]
    assert data["message"].rstrip().endswith("CANDIDATE\ntipo: text")


@pytest.mark.parametrize("decision_type", ["checkin", "proactivity"])
def test_candidate_path_for_other_decision_types_is_unchanged(monkeypatch, decision_type: str):
    monkeypatch.setenv("RELIC_CHECKIN_POLICY_ENABLED", "1")

    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock, \
         patch("relic.gumi_plugin.cron_wiring._apply_naturalness_policy") as naturalness_mock, \
         patch("relic.gumi_plugin.cron_wiring._run_outcome_reconciler"):
        eval_mock.return_value = (
            RuntimeDecision.CANDIDATE,
            [],
            {"message": "CANDIDATE\ntipo: text"},
        )
        decision, _, data = make_decision("s1", "g1", "p1", decision_type=decision_type)

    naturalness_mock.assert_not_called()
    assert decision == RuntimeDecision.CANDIDATE
    assert data == {"message": "CANDIDATE\ntipo: text"}
