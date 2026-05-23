"""Focused tests for continuity_preference in checkin policy/features."""

from __future__ import annotations

import json
from pathlib import Path

from relic.checkin.features import build_checkin_features
from relic.checkin.policy import CheckinFeatures, EventType, Posture, select_decision


def _enabled(**overrides) -> dict:
    return {
        "policy_enabled": True,
        **overrides,
    }


def test_continuity_preference_neutral_matches_default_policy_decisions():
    ask_default = CheckinFeatures(
        reach_score=1.0,
        topic_freshness=0.61,
        facet_status="ask_now",
        asked_recently_12h=False,
        time_since_last_subject_msg_sec=3 * 3600,
    )
    ask_neutral = CheckinFeatures(
        continuity_preference=0.5,
        reach_score=1.0,
        topic_freshness=0.61,
        facet_status="ask_now",
        asked_recently_12h=False,
        time_since_last_subject_msg_sec=3 * 3600,
    )

    reflect_default = CheckinFeatures(
        reach_score=1.0,
        importance_accumulator=0.81,
        last_reflect_age_days=7,
        time_since_last_subject_msg_sec=3 * 3600,
    )
    reflect_neutral = CheckinFeatures(
        continuity_preference=0.5,
        reach_score=1.0,
        importance_accumulator=0.81,
        last_reflect_age_days=7,
        time_since_last_subject_msg_sec=3 * 3600,
    )

    ask_default_decision = select_decision(ask_default, decision_type="checkin", **_enabled())
    ask_neutral_decision = select_decision(ask_neutral, decision_type="checkin", **_enabled())
    reflect_default_decision = select_decision(
        reflect_default,
        decision_type="checkin",
        **_enabled(reflection_enabled=True),
    )
    reflect_neutral_decision = select_decision(
        reflect_neutral,
        decision_type="checkin",
        **_enabled(reflection_enabled=True),
    )

    assert ask_neutral_decision == ask_default_decision
    assert ask_neutral_decision.posture is Posture.ASK
    assert reflect_neutral_decision == reflect_default_decision
    assert reflect_neutral_decision.posture is Posture.REFLECTIVE_MIRROR


def test_continuity_preference_high_triggers_ask_and_reflection_sooner():
    ask_neutral = CheckinFeatures(
        continuity_preference=0.5,
        reach_score=1.0,
        topic_freshness=0.5,
        facet_status="ask_now",
        asked_recently_12h=False,
        time_since_last_subject_msg_sec=3 * 3600,
    )
    ask_high = CheckinFeatures(
        continuity_preference=1.0,
        reach_score=1.0,
        topic_freshness=0.5,
        facet_status="ask_now",
        asked_recently_12h=False,
        time_since_last_subject_msg_sec=3 * 3600,
    )

    reflect_neutral = CheckinFeatures(
        continuity_preference=0.5,
        reach_score=1.0,
        importance_accumulator=0.7,
        last_reflect_age_days=4,
        time_since_last_subject_msg_sec=3 * 3600,
    )
    reflect_high = CheckinFeatures(
        continuity_preference=1.0,
        reach_score=1.0,
        importance_accumulator=0.7,
        last_reflect_age_days=4,
        time_since_last_subject_msg_sec=3 * 3600,
    )

    ask_neutral_decision = select_decision(ask_neutral, decision_type="checkin", **_enabled())
    ask_high_decision = select_decision(ask_high, decision_type="checkin", **_enabled())
    reflect_neutral_decision = select_decision(
        reflect_neutral,
        decision_type="checkin",
        **_enabled(reflection_enabled=True),
    )
    reflect_high_decision = select_decision(
        reflect_high,
        decision_type="checkin",
        **_enabled(reflection_enabled=True),
    )

    assert ask_neutral_decision.event_type is EventType.SILENT
    assert ask_neutral_decision.reason == "checkin_no_facet_target"
    assert ask_high_decision.posture is Posture.ASK
    assert reflect_neutral_decision.event_type is EventType.SILENT
    assert reflect_neutral_decision.reason == "checkin_no_facet_target"
    assert reflect_high_decision.event_type is EventType.REFLECTION
    assert reflect_high_decision.posture is Posture.REFLECTIVE_MIRROR


def test_build_checkin_features_loads_continuity_preference_with_fallbacks(tmp_path: Path):
    relic_home = tmp_path / "relic"
    hermes_home = tmp_path / "hermes"
    subject_dir = relic_home / "subjects" / "s1"
    subject_dir.mkdir(parents=True)

    (subject_dir / "item_battery_response.json").write_text(
        json.dumps(
            {
                "scores": {
                    "project_calibration": {
                        "continuity_preference": 0.8,
                        "comfort_with_initiative": 0.7,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    features = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert features.continuity_preference == 0.8
    assert features.comfort_with_initiative == 0.7

    (subject_dir / "item_battery_response.json").unlink()
    (subject_dir / "subject_baseline.json").write_text(
        json.dumps(
            {
                "item_battery": {
                    "scores": {
                        "project_calibration": {
                            "continuity_preference": 0.3,
                            "comfort_with_initiative": 0.2,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    features = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert features.continuity_preference == 0.3
    assert features.comfort_with_initiative == 0.2

    (subject_dir / "subject_baseline.json").unlink()
    features = build_checkin_features(
        subject_id="s1",
        decision_type="checkin",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert features.continuity_preference == 0.5
    assert features.comfort_with_initiative == 0.5
