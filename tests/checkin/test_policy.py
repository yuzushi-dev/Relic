"""Tests for relic.checkin.policy — types + minimal selector."""

from __future__ import annotations

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
