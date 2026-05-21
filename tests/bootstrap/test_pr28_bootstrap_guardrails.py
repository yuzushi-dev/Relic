"""Focused bootstrap guardrail tests for project-level safety defaults."""
from __future__ import annotations

import json
from pathlib import Path

import relic.bootstrap as bootstrap
from relic.bootstrap import build_pr28_bootstrap_outputs, subject_data_from_bootstrap_state


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _subject_fixture() -> dict:
    return {
        "subject_id": "subj_001",
        "experiment_id": "exp_001",
        "psychological": {
            "openness": 0.70,
            "conscientiousness": 0.55,
            "extraversion": 0.35,
            "agreeableness": 0.65,
            "emotional_stability": 0.40,
            "attachment_anxiety": 0.82,
            "attachment_avoidance": 0.20,
        },
        "interaction": {
            "directness_preference": 0.60,
            "critique_tolerance": 0.55,
            "proactive_contact_tolerance": 0.30,
            "checkin_tolerance": 0.45,
            "humor_tolerance": 0.50,
            "ambiguity_tolerance": 0.45,
            "emotional_intensity_tolerance": 0.40,
            "fictional_diegesis_tolerance": 0.80,
            "audio_tolerance": 0.20,
            "image_tolerance": 0.65,
            "music_tolerance": 0.30,
        },
        "relational": {
            "desired_closeness": 0.70,
            "preferred_distance": 0.45,
            "comfort_with_initiative": 0.35,
            "comfort_with_warmth": 0.75,
            "comfort_with_disagreement": 0.50,
            "comfort_with_mystery": 0.55,
            "comfort_with_Gumi_having_her_own_life": 0.85,
            "comfort_with_Gumi_saying_no": 0.80,
        },
        "boundary": {
            "romantic_escalation_allowed": False,
            "dependency_risk_watch": "standard",
            "high_stakes_topics_allowed": False,
            "health_nudges_allowed": False,
            "late_night_messages_allowed": False,
            "audio_allowed": False,
            "image_allowed": True,
            "music_allowed": False,
            "diegetic_life_fragments_allowed": True,
            "maximum_daily_initiatives": 1,
            "opt_out_categories": ["mental_health_treatment"],
            "quiet_hours": {"start": "22:00", "end": "08:00", "timezone": "Europe/Rome"},
            "careful_distancing_enabled": True,
            "sensitive_topics_blocked": True,
        },
    }


def test_boundary_policy_hard_locks_project_guardrails_when_safe_scores_are_zero(tmp_path: Path) -> None:
    subject = subject_data_from_bootstrap_state(
        subject_id="subj_001",
        experiment_id="exp_001",
        state={
            "item_battery": {
                "scores": {
                    "project_calibration": {
                        "external_support_on_dependency": 0,
                        "high_stakes_proactive_block": 0,
                        "dependency_risk_requires_review": 0,
                    },
                    "safety_boundary_gates": {
                        "external_support_on_dependency": 0,
                        "high_stakes_proactive_block": 0,
                        "dependency_risk_requires_review": 0,
                    },
                }
            }
        },
    )

    outputs = build_pr28_bootstrap_outputs(tmp_path, subject, generation_mode="hybrid", seed=11)
    policy = _load(outputs["boundary_policy"])

    assert policy["high_stakes_proactive_block"] is True
    assert policy["dependency_risk_requires_review"] is True
    assert policy["external_support_on_dependency"] is True


def test_high_dependency_risk_sets_review_required_guardrail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_clamp", lambda value: round(float(value), 3))
    subject = _subject_fixture()
    subject["psychological"]["attachment_anxiety"] = 2.0
    subject["interaction"]["proactive_contact_tolerance"] = 2.0
    subject["boundary"]["careful_distancing_enabled"] = False
    subject["boundary"]["sensitive_topics_blocked"] = False

    outputs = build_pr28_bootstrap_outputs(tmp_path, subject, generation_mode="hybrid", seed=12)
    policy = _load(outputs["boundary_policy"])
    constraints = _load(outputs["gumi_generation_constraints"])
    report = _load(outputs["sweet_spot_report"])

    assert report["scores"]["dependency_risk"] >= 0.6
    assert policy["requires_review_on_dependency"] is True
    assert constraints["researcher_review_required"] is True


def test_guardrails_are_carried_into_constraints(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="hybrid", seed=13)
    constraints = _load(outputs["gumi_generation_constraints"])

    assert constraints["initiative"]["high_stakes_topics_blocked"] is True
    assert constraints["relationship"]["external_support_on_dependency"] is True
