"""Focused tests for the diegetic check-in scaffold."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from relic.checkin.features import build_checkin_features
from relic.checkin.policy import CheckinFeatures, Decision, EventType, Posture, select_decision


def _enabled(**overrides) -> dict:
    return {
        "policy_enabled": True,
        **overrides,
    }


def test_diegetic_decision_path_is_explicit_and_existing_paths_stay_unchanged():
    disabled = CheckinFeatures(
        diegetic_enabled=False,
        diegetic_tolerance=0.9,
    )
    disabled_decision = select_decision(
        disabled,
        decision_type="diegetic",
        **_enabled(),
    )

    enabled_share = CheckinFeatures(
        diegetic_enabled=True,
        diegetic_tolerance=0.5,
    )
    share_decision = select_decision(
        enabled_share,
        decision_type="diegetic",
        **_enabled(),
    )

    enabled_below_tolerance = CheckinFeatures(
        diegetic_enabled=True,
        diegetic_tolerance=0.49,
    )
    below_tolerance_decision = select_decision(
        enabled_below_tolerance,
        decision_type="diegetic",
        **_enabled(),
    )

    unchanged_checkin = select_decision(
        CheckinFeatures(
            reach_score=1.0,
            time_since_last_subject_msg_sec=3 * 3600,
            salience_top=0.1,
        ),
        decision_type="checkin",
        **_enabled(),
    )
    unchanged_proactivity = select_decision(
        CheckinFeatures(
            reach_score=1.0,
            salience_top=0.8,
            time_since_last_subject_msg_sec=5 * 3600,
        ),
        decision_type="proactivity",
        **_enabled(),
    )

    assert disabled_decision == Decision(
        EventType.SILENT,
        Posture.QUIET,
        "diegetic_disabled",
    )
    assert share_decision == Decision(
        EventType.DIEGETIC,
        Posture.SMALL_SHARE,
        "diegetic_share",
    )
    assert below_tolerance_decision == Decision(
        EventType.SILENT,
        Posture.QUIET,
        "diegetic_below_tolerance",
    )
    assert unchanged_checkin.event_type is EventType.CHECKIN
    assert unchanged_checkin.posture is Posture.OBSERVE
    assert unchanged_proactivity.event_type is EventType.PROACTIVE
    assert unchanged_proactivity.posture is Posture.BRIEF_SHARE


def test_diegetic_none_runtime_knobs_keep_scaffold_behavior():
    features = CheckinFeatures(
        diegetic_enabled=True,
        diegetic_tolerance=0.5,
        diegetic_intensity=None,
        diegetic_frequency=None,
    )

    decision = select_decision(
        features,
        decision_type="diegetic",
        **_enabled(),
    )

    assert decision == Decision(
        EventType.DIEGETIC,
        Posture.SMALL_SHARE,
        "diegetic_share",
    )


def test_diegetic_frequency_backoff_preempts_tolerance_share():
    decision = select_decision(
        CheckinFeatures(
            diegetic_enabled=True,
            diegetic_tolerance=0.9,
            diegetic_frequency=0.24,
        ),
        decision_type="diegetic",
        **_enabled(),
    )

    assert decision == Decision(
        EventType.SILENT,
        Posture.QUIET,
        "diegetic_frequency_backoff",
    )


def test_diegetic_daily_cap_short_circuits_silent():
    decision = select_decision(
        CheckinFeatures(
            diegetic_enabled=True,
            diegetic_tolerance=0.9,
            diegetic_today=1,
        ),
        decision_type="diegetic",
        **_enabled(),
    )

    assert decision == Decision(
        EventType.SILENT,
        Posture.QUIET,
        "diegetic_daily_cap",
    )


@pytest.mark.parametrize(
    ("intensity", "posture", "reason"),
    [
        (0.49, Posture.SMALL_SHARE, "diegetic_share_factual"),
        (0.5, Posture.BRIEF_SHARE, "diegetic_share_warm"),
    ],
)
def test_diegetic_intensity_grades_share_posture(intensity, posture, reason):
    decision = select_decision(
        CheckinFeatures(
            diegetic_enabled=True,
            diegetic_tolerance=0.9,
            diegetic_intensity=intensity,
        ),
        decision_type="diegetic",
        **_enabled(),
    )

    assert decision == Decision(
        EventType.DIEGETIC,
        posture,
        reason,
    )


def test_build_checkin_features_loads_diegetic_tolerance_from_calibration_fallbacks(
    tmp_path: Path,
):
    relic_home = tmp_path / "relic"
    hermes_home = tmp_path / "hermes"
    subject_dir = relic_home / "subjects" / "s1"
    subject_dir.mkdir(parents=True)

    (subject_dir / "subject_baseline.json").write_text(
        json.dumps(
            {
                "item_battery": {
                    "scores": {
                        "project_calibration": {
                            "fictional_diegesis_tolerance": 0.72,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    features = build_checkin_features(
        subject_id="s1",
        decision_type="diegetic",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert features.diegetic_tolerance == 0.72
    assert features.diegetic_enabled is False

    (subject_dir / "subject_baseline.json").write_text(
        json.dumps(
            {
                "item_battery": {
                    "scores": {
                        "project_calibration": {
                            "embodiment_world_tolerance": 0.2,
                            "routine_fragment_tolerance": 0.4,
                            "first_person_life_fragment_tolerance": 0.6,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    features = build_checkin_features(
        subject_id="s1",
        decision_type="diegetic",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert features.diegetic_tolerance == pytest.approx(0.4)

    (subject_dir / "subject_baseline.json").write_text(
        json.dumps({}),
        encoding="utf-8",
    )
    features = build_checkin_features(
        subject_id="s1",
        decision_type="diegetic",
        relic_home=relic_home,
        hermes_home=hermes_home,
    )
    assert features.diegetic_tolerance == 0.45
