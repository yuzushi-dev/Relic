"""PR28 bootstrap contract tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

pytestmark = pytest.mark.slow

from relic.bootstrap import (
    BootstrapCheckpointStore,
    build_pr28_bootstrap_outputs,
    resume_bootstrap_session,
    subject_data_from_bootstrap_state,
)


def _subject_fixture(**overrides: object) -> dict:
    baseline = {
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
    baseline.update(overrides)
    return baseline


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(schema_path: str, payload: dict) -> list:
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    return list(Draft7Validator(schema).iter_errors(payload))


def test_bootstrap_creates_subject_baseline(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="hybrid", seed=42)
    baseline = _load(outputs["subject_baseline"])

    assert baseline["subject_id"] == "subj_001"
    assert baseline["psychological"]["attachment_anxiety"]["value"] == 0.82
    assert baseline["psychological"]["attachment_anxiety"]["confidence"] == "low_initial"
    assert _validate("schemas/bootstrap/subject_baseline.schema.json", baseline) == []


def test_bootstrap_creates_gumi_instance(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="hybrid", seed=42)
    candidate = _load(outputs["gumi_profile_candidate"])

    assert candidate["subject_id"] == "subj_001"
    assert candidate["gumi_instance_id"] == "gumi_subj_001"
    assert candidate["vectors"]["similarity"] <= 0.80
    assert candidate["vectors"]["similarity"] >= 0.35
    assert candidate["traits"]["careful_distancing"] is True
    assert _validate("schemas/bootstrap/gumi_profile_candidate.schema.json", candidate) == []


def test_bootstrap_creates_sweet_spot_report(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="hybrid", seed=42)
    report = _load(outputs["sweet_spot_report"])

    assert report["algorithm_version"] == "sweetspot_v1"
    assert report["scores"]["dependency_risk"] >= 0.0
    assert "keep careful distancing enabled" in report["recommended_adjustments"]
    assert report["review_status"] == "researcher_review_required"
    assert _validate("schemas/bootstrap/sweet_spot_report.schema.json", report) == []


def test_high_attachment_anxiety_enables_careful_distancing(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="random", seed=1)
    policy = _load(outputs["boundary_policy"])
    constraints = _load(outputs["gumi_generation_constraints"])

    assert policy["careful_distancing_enabled"] is True
    assert constraints["relationship"]["romantic_ambiguity"] == "reduced"
    assert constraints["initiative"]["availability"] != "hyper_available"


def test_low_proactive_tolerance_limits_initiative(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="random", seed=2)
    constraints = _load(outputs["gumi_generation_constraints"])

    assert constraints["initiative"]["mode"] == "review_required"
    assert constraints["initiative"]["maximum_daily_initiatives"] == 1


def test_high_diegetic_tolerance_allows_life_fragments(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="random", seed=3)
    tolerance = _load(outputs["diegetic_tolerance_profile"])

    assert tolerance["life_fragments"]["mode"] == "review_required"
    assert tolerance["diegetic_density"]["target"] == "high"


def test_low_diegetic_tolerance_blocks_media_by_default(tmp_path: Path) -> None:
    subject = _subject_fixture()
    subject["interaction"]["fictional_diegesis_tolerance"] = 0.10
    subject["interaction"]["image_tolerance"] = 0.10
    outputs = build_pr28_bootstrap_outputs(tmp_path, subject, generation_mode="random", seed=4)
    tolerance = _load(outputs["diegetic_tolerance_profile"])

    assert tolerance["life_fragments"]["mode"] == "disabled"
    assert tolerance["image"]["mode"] == "disabled"


def test_gumi_not_clone_of_subject(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="random", seed=5)
    report = _load(outputs["sweet_spot_report"])

    assert report["scores"]["clone_risk"] < 0.80
    assert report["scores"]["sweet_spot_score"] > 0.0


def test_gumi_not_arbitrary_opposite(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="random", seed=6)
    report = _load(outputs["sweet_spot_report"])

    assert report["scores"]["alienation_risk"] < 0.80


def test_first_contact_not_template(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="hybrid", seed=7)
    first_contact = _load(outputs["first_contact_candidate"])

    assert first_contact["template_used"] is False
    assert first_contact["composition_mode"] == "generated_from_constraints"
    assert first_contact["forbidden_pattern_check"]["passed"] is True
    assert "baseline_inputs_used" in first_contact


def test_bootstrap_outputs_are_versioned(tmp_path: Path) -> None:
    outputs = build_pr28_bootstrap_outputs(tmp_path, _subject_fixture(), generation_mode="hybrid", seed=8)
    for path in outputs.values():
        payload = _load(path)
        assert payload["schema_version"]
        assert payload["version"] == 1
        assert payload["created_at"]


def test_bootstrap_resume_from_checkpoint(tmp_path: Path) -> None:
    store = BootstrapCheckpointStore(tmp_path)
    session_id = "boot_subj_001"
    store.write_checkpoint(session_id, 1, "Select Study / Create Subject", {"subject_id": "subj_001"})
    store.write_checkpoint(session_id, 2, "Consent and Scope", {"delivery": False})

    resumed = resume_bootstrap_session(tmp_path, session_id)

    assert resumed["bootstrap_session_id"] == session_id
    assert resumed["latest_checkpoint"]["screen_number"] == 2
    assert len(resumed["checkpoints"]) == 2


def test_low_frequency_preference_damps_contact_cadence_only_above_neutral() -> None:
    state = {
        "item_battery": {
            "scores": {
                "project_calibration": {
                    "proactive_permission": 0.8,
                    "checkin_permission": 1.0,
                }
            }
        }
    }
    consent_record = {"delivery": True}

    default_subject = subject_data_from_bootstrap_state(
        subject_id="subj_001",
        experiment_id="exp_001",
        state=state,
        consent_record=consent_record,
    )
    neutral_subject = subject_data_from_bootstrap_state(
        subject_id="subj_001",
        experiment_id="exp_001",
        state={
            "item_battery": {
                "scores": {
                    "project_calibration": {
                        "proactive_permission": 0.8,
                        "checkin_permission": 1.0,
                        "low_frequency_preference": 0.5,
                    }
                }
            }
        },
        consent_record=consent_record,
    )
    damped_subject = subject_data_from_bootstrap_state(
        subject_id="subj_001",
        experiment_id="exp_001",
        state={
            "item_battery": {
                "scores": {
                    "project_calibration": {
                        "proactive_permission": 0.8,
                        "checkin_permission": 1.0,
                        "low_frequency_preference": 1.0,
                    }
                }
            }
        },
        consent_record=consent_record,
    )

    assert default_subject["boundary"]["maximum_daily_initiatives"] == 2
    assert default_subject["interaction"]["proactive_contact_tolerance"] == 0.8
    assert neutral_subject["boundary"]["maximum_daily_initiatives"] == 2
    assert neutral_subject["interaction"]["proactive_contact_tolerance"] == 0.8
    assert damped_subject["boundary"]["maximum_daily_initiatives"] == 1
    assert damped_subject["interaction"]["proactive_contact_tolerance"] == 0.0
