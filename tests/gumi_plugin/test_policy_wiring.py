"""Tests for cron_wiring.make_decision → naturalness policy wiring (Plan §Task 7)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from relic.checkin.policy import CheckinFeatures
from relic.gumi_plugin.cron_wiring import _evaluate_decision, make_decision
from relic.hermes_runtime import RuntimeDecision, RuntimeDecisionReason


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
            return_value=Decision(EventType.CHECKIN, Posture.ASK, "topic_fresh_and_ask_ready"),
        ):
            decision, _, data = make_decision("s1", "g1", "p1", decision_type="checkin")
    assert decision == RuntimeDecision.DELIVER
    assert data is not None
    assert data["event_type"] == "checkin"
    assert data["posture"] == "ask"
    assert "[EVENTO: checkin]" in data["message"]
    assert "con domanda" in data["message"]
    assert data["message"].rstrip().endswith("DELIVER\ntipo: text")


def test_force_checkin_with_ask_prepends_question_constraint_header(monkeypatch):
    monkeypatch.delenv("RELIC_CHECKIN_POLICY_ENABLED", raising=False)

    with patch("relic.gumi_plugin.cron_wiring._run_outcome_reconciler"), \
         patch("relic.gumi_plugin.cron_wiring._select_media_type", return_value="text"), \
         patch(
             "relic.gumi_plugin.cron_wiring._select_ask_decision",
             return_value=(True, "Velocità nel decidere"),
         ):
        decision, _, data = make_decision(
            "s1",
            "g1",
            "p1",
            decision_type="checkin",
            force=True,
        )

    assert decision == RuntimeDecision.DELIVER
    assert data is not None
    assert "[POSTURA: ask]" in data["message"]
    assert "con domanda" in data["message"]
    assert "ask_topic: Velocità nel decidere" in data["message"]


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


@pytest.mark.parametrize("decision_type", ["diegetic", "proactivity"])
def test_evaluate_decision_routes_naturalness_types_to_candidate(monkeypatch, decision_type: str):
    with patch("relic.gumi_plugin.cron_wiring._is_globally_paused", return_value=False), \
         patch("relic.gumi_plugin.cron_wiring._pro_checkin_allowed", return_value=True), \
         patch("relic.gumi_plugin.cron_wiring._is_quiet_hours", return_value=False), \
         patch("relic.gumi_plugin.cron_wiring._is_platform_not_allowlisted", return_value=False), \
         patch("relic.gumi_plugin.cron_wiring._is_subject_paused", return_value=False), \
         patch("relic.gumi_plugin.cron_wiring._is_continuity_scope_paused", return_value=False), \
         patch("relic.gumi_plugin.cron_wiring.get_continuity_service") as svc_mock, \
         patch("relic.gumi_plugin.cron_wiring._is_delivery_window_open") as delivery_window_mock:
        decision, reasons, data = _evaluate_decision("s1", "g1", "p1", decision_type=decision_type)

    svc_mock.assert_not_called()
    delivery_window_mock.assert_not_called()
    assert decision == RuntimeDecision.CANDIDATE
    assert reasons == [RuntimeDecisionReason.no_due_work]
    # Gate now emits a complete DELIVER header (tipo + ora) so the diegetic/
    # proactive composer is time-aware; the naturalness policy still gates whether
    # this becomes a real initiative.
    assert data is not None
    msg = data["message"]
    assert msg.startswith("DELIVER\ntipo: ")
    assert "\nora: " in msg


@pytest.mark.parametrize(
    ("decision_type", "gate_patch", "expected_decision", "expected_reason"),
    [
        ("diegetic", "_is_subject_paused", RuntimeDecision.BLOCKED, RuntimeDecisionReason.subject_paused),
        ("diegetic", "_is_quiet_hours", RuntimeDecision.BLOCKED, RuntimeDecisionReason.quiet_hours),
        ("proactivity", "_is_platform_not_allowlisted", RuntimeDecision.BLOCKED, RuntimeDecisionReason.platform_not_allowlisted),
        (
            "proactivity",
            "_is_continuity_scope_paused",
            RuntimeDecision.BLOCKED,
            RuntimeDecisionReason.continuity_scope_paused,
        ),
    ],
)
def test_evaluate_decision_safety_gates_still_block_naturalness_types(
    monkeypatch,
    decision_type: str,
    gate_patch: str,
    expected_decision: RuntimeDecision,
    expected_reason: RuntimeDecisionReason,
):
    patches = {
        "_is_globally_paused": False,
        "_pro_checkin_allowed": True,
        "_is_quiet_hours": False,
        "_is_platform_not_allowlisted": False,
        "_is_subject_paused": False,
        "_is_continuity_scope_paused": False,
    }
    patches[gate_patch] = True

    with patch("relic.gumi_plugin.cron_wiring._is_globally_paused", return_value=patches["_is_globally_paused"]), \
         patch("relic.gumi_plugin.cron_wiring._pro_checkin_allowed", return_value=patches["_pro_checkin_allowed"]), \
         patch("relic.gumi_plugin.cron_wiring._is_quiet_hours", return_value=patches["_is_quiet_hours"]), \
         patch(
             "relic.gumi_plugin.cron_wiring._is_platform_not_allowlisted",
             return_value=patches["_is_platform_not_allowlisted"],
         ), \
         patch("relic.gumi_plugin.cron_wiring._is_subject_paused", return_value=patches["_is_subject_paused"]), \
         patch(
             "relic.gumi_plugin.cron_wiring._is_continuity_scope_paused",
             return_value=patches["_is_continuity_scope_paused"],
         ), \
         patch("relic.gumi_plugin.cron_wiring.get_continuity_service") as svc_mock:
        decision, reasons, data = _evaluate_decision("s1", "g1", "p1", decision_type=decision_type)

    svc_mock.assert_not_called()
    assert decision == expected_decision
    assert reasons == [expected_reason]
    assert data is None


def test_policy_enabled_proactivity_candidate_returns_no_reply_when_silent(monkeypatch):
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
                comfort_with_initiative=0.1,
                reach_score=1.0,
                salience_top=0.9,
                time_since_last_subject_msg_sec=7200,
            ),
        ) as features_mock:
            decision, _, data = make_decision("s1", "g1", "p1", decision_type="proactivity")

    assert features_mock.call_args.kwargs["decision_type"] == "proactivity"
    assert decision == RuntimeDecision.NO_REPLY
    assert data is None


def test_policy_enabled_proactivity_candidate_honors_non_silent_decision(monkeypatch):
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
                comfort_with_initiative=0.5,
                reach_score=1.0,
                salience_top=0.7,
                time_since_last_subject_msg_sec=7200,
            ),
        ) as features_mock:
            decision, _, data = make_decision("s1", "g1", "p1", decision_type="proactivity")

    assert features_mock.call_args.kwargs["decision_type"] == "proactivity"
    assert decision == RuntimeDecision.CANDIDATE
    assert data is not None
    assert data["event_type"] == "proactive"
    assert data["posture"] == "brief_share"
    assert "[EVENTO: proactive]" in data["message"]
    assert data["message"].rstrip().endswith("CANDIDATE\ntipo: text")


def test_candidate_path_for_checkin_is_unchanged(monkeypatch):
    monkeypatch.setenv("RELIC_CHECKIN_POLICY_ENABLED", "1")

    with patch("relic.gumi_plugin.cron_wiring._evaluate_decision") as eval_mock, \
         patch("relic.gumi_plugin.cron_wiring._apply_naturalness_policy") as naturalness_mock, \
         patch("relic.gumi_plugin.cron_wiring._run_outcome_reconciler"):
        eval_mock.return_value = (
            RuntimeDecision.CANDIDATE,
            [],
            {"message": "CANDIDATE\ntipo: text"},
        )
        decision, _, data = make_decision("s1", "g1", "p1", decision_type="checkin")

    naturalness_mock.assert_not_called()
    assert decision == RuntimeDecision.CANDIDATE
    assert data == {"message": "CANDIDATE\ntipo: text"}
