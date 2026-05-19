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
