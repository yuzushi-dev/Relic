"""Scenario tests for select_decision (spike §12.3 / §15)."""

from __future__ import annotations

from relic.checkin.policy import (
    CheckinFeatures,
    Decision,
    EventType,
    Posture,
    select_decision,
)


def _enabled(**overrides) -> dict:
    return {
        "policy_enabled": True,
        **overrides,
    }


def test_scenario_lightweight_checkin_without_facet_is_silent():
    f = CheckinFeatures(
        reach_score=1.0,
        time_since_last_subject_msg_sec=3 * 3600,
        salience_top=0.1,
    )
    d = select_decision(f, decision_type="checkin", **_enabled())
    assert d.event_type is EventType.SILENT
    assert d.posture is Posture.QUIET
    assert d.reason == "checkin_no_facet_target"


def test_scenario_followup_warm_first_attempt():
    f = CheckinFeatures(reach_score=1.0, time_since_last_subject_msg_sec=3600)
    d = select_decision(f, decision_type="followup", **_enabled())
    assert d.event_type is EventType.FOLLOWUP
    assert d.posture is Posture.FOLLOW_UP_WARM


def test_scenario_followup_terse_after_silence():
    f = CheckinFeatures(
        reach_score=0.7,
        non_response_streak=1,
        time_since_last_subject_msg_sec=3600,
    )
    d = select_decision(f, decision_type="followup", **_enabled())
    assert d.event_type is EventType.FOLLOWUP
    assert d.posture is Posture.FOLLOW_UP_TERSE


def test_scenario_proactive_brief_share_when_salient():
    f = CheckinFeatures(
        reach_score=1.0,
        salience_top=0.8,
        time_since_last_subject_msg_sec=5 * 3600,
    )
    d = select_decision(f, decision_type="proactivity", **_enabled())
    assert d.event_type is EventType.PROACTIVE
    assert d.posture is Posture.BRIEF_SHARE


def test_scenario_silent_after_three_unanswered():
    f = CheckinFeatures(
        non_response_streak=3,
        reach_score=0.343,
        time_since_last_subject_msg_sec=24 * 3600,
    )
    d = select_decision(f, decision_type="checkin", **_enabled())
    assert d.event_type is EventType.SILENT


def test_scenario_risk_flag_forces_silent_even_with_high_salience():
    f = CheckinFeatures(
        risk_flag_active=True,
        salience_top=0.9,
        reach_score=1.0,
    )
    d = select_decision(f, decision_type="proactivity", **_enabled())
    assert d.event_type is EventType.SILENT
    assert d.reason == "risk_flag_active"


def test_scenario_brief_share_no_longer_used_for_checkin():
    f = CheckinFeatures(
        reach_score=1.0,
        salience_top=0.5,
        subject_avg_tokens_14d=4.0,
        time_since_last_subject_msg_sec=3 * 3600,
    )
    d = select_decision(f, decision_type="checkin", **_enabled())
    assert d.event_type is EventType.SILENT
    assert d.reason == "checkin_no_facet_target"


def test_scenario_reflection_remains_disabled_by_default():
    f = CheckinFeatures(
        reach_score=1.0,
        importance_accumulator=0.9,
        last_reflect_age_days=10,
        time_since_last_subject_msg_sec=3 * 3600,
    )
    d = select_decision(f, decision_type="checkin", **_enabled())
    assert d.event_type is EventType.SILENT
    assert d.reason == "reflection_disabled"


def test_scenario_ask_when_topic_fresh_and_facet_ready():
    f = CheckinFeatures(
        reach_score=1.0,
        topic_freshness=0.9,
        facet_status="ask_now",
        asked_recently_12h=False,
        time_since_last_subject_msg_sec=3 * 3600,
    )
    d = select_decision(f, decision_type="checkin", **_enabled())
    assert d.event_type is EventType.CHECKIN
    assert d.posture is Posture.ASK


def test_ask_scenario_emits_constraint_header():
    from relic.checkin.policy import apply_constraint_header

    f = CheckinFeatures(
        reach_score=1.0,
        time_since_last_subject_msg_sec=3600,
        facet_status="ask_now",
        asked_recently_12h=False,
    )
    decision = select_decision(f, decision_type="checkin", policy_enabled=True)
    out = apply_constraint_header("DELIVER\ntipo: text", decision)
    assert "[EVENTO: checkin]" in out
    assert "[POSTURA: ask]" in out
    assert "con domanda" in out


def test_silent_scenario_emits_no_header():
    from relic.checkin.policy import apply_constraint_header

    f = CheckinFeatures(risk_flag_active=True)
    decision = select_decision(f, decision_type="checkin", policy_enabled=True)
    out = apply_constraint_header("DELIVER\ntipo: text", decision)
    assert "[EVENTO:" not in out


def test_scenario_ask_blocked_when_last_ask_got_no_reply():
    """Spike §9.5: forbid ask→ask only after a non-response."""
    f = CheckinFeatures(
        reach_score=1.0,
        topic_freshness=0.9,
        facet_status="ask_now",
        asked_recently_12h=False,
        time_since_last_subject_msg_sec=3 * 3600,
        posture_history_last_5=[Posture.ASK.value],
        non_response_streak=1,
    )
    d = select_decision(f, decision_type="checkin", **_enabled())
    assert d.posture is not Posture.ASK


def test_scenario_ask_allowed_again_after_reply():
    """A subject reply resets the streak; ASK→ASK becomes allowed."""
    f = CheckinFeatures(
        reach_score=1.0,
        topic_freshness=0.9,
        facet_status="ask_now",
        asked_recently_12h=False,
        time_since_last_subject_msg_sec=3 * 3600,
        posture_history_last_5=[Posture.ASK.value],
        non_response_streak=0,
    )
    d = select_decision(f, decision_type="checkin", **_enabled())
    assert d.posture is Posture.ASK


def test_proactive_brief_share_blocked_when_subject_laconic():
    """Reviewer fix: §9.5 forbidden brief_share must apply to proactivity too."""
    f = CheckinFeatures(
        reach_score=1.0,
        salience_top=0.8,
        subject_avg_tokens_14d=4.0,
        time_since_last_subject_msg_sec=7200,
    )
    d = select_decision(f, decision_type="proactivity", policy_enabled=True)
    assert d.event_type is EventType.SILENT
    assert d.reason == "proactive_subject_laconic"


def test_frequency_cap_short_circuits_silent():
    """Reviewer fix: cap is only meaningful if daily_initiatives_today is fed."""
    f = CheckinFeatures(
        reach_score=1.0,
        frequency_cap_per_day=1,
        daily_initiatives_today=1,
        time_since_last_subject_msg_sec=3600,
    )
    d = select_decision(f, decision_type="checkin", policy_enabled=True)
    assert d.event_type is EventType.SILENT
    assert d.reason == "frequency_cap_reached"
