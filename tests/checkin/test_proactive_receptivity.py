"""Focused tests for proactive receptivity gating in checkin policy."""

from __future__ import annotations

from relic.checkin.policy import CheckinFeatures, EventType, Posture, select_decision


def test_proactive_comfort_neutral_matches_default_behavior():
    default_features = CheckinFeatures(
        reach_score=1.0,
        salience_top=0.7,
        time_since_last_subject_msg_sec=7200,
    )
    neutral_features = CheckinFeatures(
        comfort_with_initiative=0.5,
        reach_score=1.0,
        salience_top=0.7,
        time_since_last_subject_msg_sec=7200,
    )

    default_decision = select_decision(
        default_features,
        decision_type="proactivity",
        policy_enabled=True,
    )
    neutral_decision = select_decision(
        neutral_features,
        decision_type="proactivity",
        policy_enabled=True,
    )

    assert neutral_decision == default_decision
    assert neutral_decision.event_type is EventType.PROACTIVE
    assert neutral_decision.posture is Posture.BRIEF_SHARE


def test_proactive_low_comfort_short_circuits_to_silent():
    features = CheckinFeatures(
        comfort_with_initiative=0.1,
        reach_score=1.0,
        salience_top=0.9,
        time_since_last_subject_msg_sec=7200,
    )

    decision = select_decision(
        features,
        decision_type="proactivity",
        policy_enabled=True,
    )

    assert decision.event_type is EventType.SILENT
    assert decision.posture is Posture.QUIET
    assert decision.reason == "proactive_low_receptivity"


def test_proactive_moderately_low_comfort_raises_salience_bar():
    neutral_features = CheckinFeatures(
        comfort_with_initiative=0.5,
        reach_score=1.0,
        salience_top=0.62,
        time_since_last_subject_msg_sec=7200,
    )
    lower_comfort_features = CheckinFeatures(
        comfort_with_initiative=0.35,
        reach_score=1.0,
        salience_top=0.62,
        time_since_last_subject_msg_sec=7200,
    )

    neutral_decision = select_decision(
        neutral_features,
        decision_type="proactivity",
        policy_enabled=True,
    )
    lower_comfort_decision = select_decision(
        lower_comfort_features,
        decision_type="proactivity",
        policy_enabled=True,
    )

    assert neutral_decision.event_type is EventType.PROACTIVE
    assert neutral_decision.reason == "proactive_salient"
    assert lower_comfort_decision.event_type is EventType.SILENT
    assert lower_comfort_decision.reason == "proactive_below_salience"
