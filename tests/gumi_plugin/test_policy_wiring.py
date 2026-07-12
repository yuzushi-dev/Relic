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
    # Bug (3) fix: silent decisions now carry policy_reason through instead of
    # collapsing to a bare None, so the caller can still log *why* it was silent.
    assert data is not None
    assert "message" not in data
    assert data["policy_reason"] == "test"


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
    assert data is not None
    assert "message" not in data
    assert data["policy_reason"] == "diegetic_disabled"


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
    assert data is not None
    assert "message" not in data
    assert data["policy_reason"] == "proactive_low_receptivity"


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


def test_apply_naturalness_policy_silent_carries_policy_reason():
    """Bug (3): _apply_naturalness_policy's silent branch used to discard the
    specific policy reason (e.g. "diegetic_frequency_backoff") by returning
    candidate_data=None, so decision logs only ever showed the generic
    no_due_work reason code. It must now surface it in the returned dict."""
    from relic.checkin.policy import Decision, EventType, Posture
    from relic.gumi_plugin.cron_wiring import _apply_naturalness_policy

    with patch(
        "relic.checkin.features.build_checkin_features",
        return_value=CheckinFeatures(subject_id="s1"),
    ), patch(
        "relic.checkin.policy.select_decision",
        return_value=Decision(EventType.SILENT, Posture.QUIET, "diegetic_frequency_backoff"),
    ):
        decision, reasons, candidate_data = _apply_naturalness_policy(
            decision=RuntimeDecision.CANDIDATE,
            reasons=[],
            candidate_data={"message": "CANDIDATE\ntipo: text"},
            subject_id="s1",
            gumi_instance_id="g1",
            hermes_profile_id="p1",
            decision_type="diegetic",
        )

    assert decision == RuntimeDecision.NO_REPLY
    assert candidate_data is not None
    assert "message" not in candidate_data
    assert candidate_data["event_type"] == "silent"
    assert candidate_data["posture"] == "quiet"
    assert candidate_data["policy_reason"] == "diegetic_frequency_backoff"


def test_rendered_script_candidate_branch_prints_deliver_context(tmp_path):
    """Bug (2): the generated no-agent script printed build_deliver_context only
    on DELIVER, but diegetic/proactivity return CANDIDATE, leaving the composer
    with a bare gate header and no material to anchor on. The rendered template
    must carry the CANDIDATE-branch context block (without consuming the
    checkin-lane topic hint)."""
    from relic.gumi_plugin.cron_wiring import render_no_agent_script

    script = render_no_agent_script(tmp_path / "relic_proactivity_decision.sh")

    candidate_branch = script.split("RuntimeDecision.CANDIDATE", 1)[1].split(
        "RuntimeDecision.DELIVER", 1
    )[0]
    assert 'decision_type in ("diegetic", "proactivity")' in candidate_branch
    assert "build_deliver_context" in candidate_branch
    assert "persist_topic_hint=False" in candidate_branch
    assert "media_type=_tipo_m" in candidate_branch
    assert "policy_reason=_cd.get(\"policy_reason\")" in script


def test_empty_anchor_context_keeps_media_modality(tmp_path):
    """A music/voice/image gate with no conversational anchors must not be
    collapsed to the 12-word text share by the no-anchor instruction: the
    media modality is handed back to the composer's own contract."""
    from relic.checkin.context_builder import build_deliver_context

    (tmp_path / "subjects" / "s1").mkdir(parents=True)
    ctx_media = build_deliver_context(
        "s1", tmp_path, tmp_path,
        event_type="proactive", posture="brief_share",
        persist_topic_hint=False, media_type="music",
    )
    assert "tipo 'music'" in ctx_media
    assert "Max 12 parole" not in ctx_media
    assert "gesto ambientale" in ctx_media

    ctx_text = build_deliver_context(
        "s1", tmp_path, tmp_path,
        event_type="proactive", posture="brief_share",
        persist_topic_hint=False, media_type="text",
    )
    assert "Max 12 parole" in ctx_text
