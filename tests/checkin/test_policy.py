"""Tests for relic.checkin.policy — types + minimal selector."""

from __future__ import annotations

import pytest

from relic.checkin.policy import CheckinFeatures, EventType, Posture, select_decision


def test_risk_flag_short_circuits_to_silent():
    f = CheckinFeatures(risk_flag_active=True)
    d = select_decision(f, decision_type="checkin")
    assert d.event_type is EventType.SILENT
    assert d.posture is Posture.QUIET


def test_stub_defaults_to_silent_until_policy_enabled():
    f = CheckinFeatures()
    d = select_decision(f, decision_type="checkin", policy_enabled=False)
    assert d.event_type is EventType.SILENT
    assert d.posture is Posture.QUIET


def test_reach_below_threshold_goes_silent():
    f = CheckinFeatures(non_response_streak=3, reach_score=0.343)
    d = select_decision(f, decision_type="checkin", policy_enabled=True)
    assert d.event_type is EventType.SILENT


def test_checkin_observe_default_when_enabled():
    f = CheckinFeatures(reach_score=1.0, time_since_last_subject_msg_sec=3600)
    d = select_decision(f, decision_type="checkin", policy_enabled=True)
    assert d.event_type is EventType.CHECKIN
    assert d.posture is Posture.OBSERVE


def test_proactivity_requires_salience():
    f = CheckinFeatures(
        reach_score=1.0,
        salience_top=0.7,
        time_since_last_subject_msg_sec=7200,
    )
    d = select_decision(f, decision_type="proactivity", policy_enabled=True)
    assert d.event_type is EventType.PROACTIVE
    assert d.posture is Posture.BRIEF_SHARE


def test_proactivity_low_salience_goes_silent():
    f = CheckinFeatures(
        reach_score=1.0,
        salience_top=0.4,
        time_since_last_subject_msg_sec=7200,
    )
    d = select_decision(f, decision_type="proactivity", policy_enabled=True)
    assert d.event_type is EventType.SILENT


def test_mid_conversation_short_circuits_silent():
    f = CheckinFeatures(reach_score=1.0, time_since_last_subject_msg_sec=30)
    d = select_decision(f, decision_type="checkin", policy_enabled=True)
    assert d.event_type is EventType.SILENT
    assert d.reason == "mid_conversation"


@pytest.mark.parametrize(
    ("decision_type", "features"),
    [
        (
            "checkin",
            CheckinFeatures(
                reach_score=1.0,
                time_since_last_subject_msg_sec=3600,
                time_since_last_initiative_sec=3600,
            ),
        ),
        (
            "followup",
            CheckinFeatures(
                reach_score=1.0,
                time_since_last_subject_msg_sec=3600,
                time_since_last_initiative_sec=3600,
            ),
        ),
        (
            "proactivity",
            CheckinFeatures(
                reach_score=1.0,
                salience_top=0.8,
                time_since_last_subject_msg_sec=7200,
                time_since_last_initiative_sec=3600,
            ),
        ),
        (
            "diegetic",
            CheckinFeatures(
                diegetic_enabled=True,
                diegetic_tolerance=0.9,
                time_since_last_initiative_sec=3600,
            ),
        ),
    ],
)
def test_initiative_spacing_short_circuits_all_decision_types(decision_type, features):
    decision = select_decision(features, decision_type=decision_type, policy_enabled=True)

    assert decision.event_type is EventType.SILENT
    assert decision.posture is Posture.QUIET
    assert decision.reason == "initiative_spacing"


@pytest.mark.parametrize("gap_seconds", [None, 5 * 3600])
def test_initiative_spacing_does_not_block_when_gap_is_none_or_large_enough(gap_seconds):
    f = CheckinFeatures(
        reach_score=1.0,
        time_since_last_subject_msg_sec=3600,
        time_since_last_initiative_sec=gap_seconds,
    )

    decision = select_decision(f, decision_type="checkin", policy_enabled=True)

    assert decision.event_type is EventType.CHECKIN
    assert decision.posture is Posture.OBSERVE
    assert decision.reason != "initiative_spacing"


def test_proactive_daily_cap_short_circuits_silent():
    f = CheckinFeatures(
        reach_score=1.0,
        salience_top=0.8,
        time_since_last_subject_msg_sec=7200,
        proactive_today=1,
    )

    decision = select_decision(f, decision_type="proactivity", policy_enabled=True)

    assert decision.event_type is EventType.SILENT
    assert decision.reason == "proactive_daily_cap"


def test_default_spacing_and_per_type_counts_preserve_current_decisions():
    checkin = select_decision(
        CheckinFeatures(
            reach_score=1.0,
            time_since_last_subject_msg_sec=3600,
            time_since_last_initiative_sec=None,
            proactive_today=0,
            diegetic_today=0,
        ),
        decision_type="checkin",
        policy_enabled=True,
    )
    proactivity = select_decision(
        CheckinFeatures(
            reach_score=1.0,
            salience_top=0.8,
            time_since_last_subject_msg_sec=7200,
            time_since_last_initiative_sec=None,
            proactive_today=0,
            diegetic_today=0,
        ),
        decision_type="proactivity",
        policy_enabled=True,
    )

    assert checkin.event_type is EventType.CHECKIN
    assert checkin.posture is Posture.OBSERVE
    assert proactivity.event_type is EventType.PROACTIVE
    assert proactivity.posture is Posture.BRIEF_SHARE
