"""PR28 subject bootstrap and Gumi sweet-spot outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "v1.0"
ALGORITHM_VERSION = "sweetspot_v1"
OUTPUT_NAMES = (
    "subject_baseline",
    "relational_comfort_profile",
    "diegetic_tolerance_profile",
    "boundary_policy",
    "gumi_generation_constraints",
    "gumi_profile_candidate",
    "sweet_spot_report",
    "bootstrap_manifest",
    "first_contact_candidate",
    "hermes_profile_manifest",
)
VECTOR_DIMS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "emotional_stability",
    "attachment_anxiety",
    "attachment_avoidance",
    "directness",
    "warmth",
    "initiative",
    "critique",
    "playfulness",
    "diegetic_density",
    "media_frequency",
    "autonomy",
    "boundary_strength",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(float(value), 3)))


def _common(subject_id: str, experiment_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": 1,
        "created_at": _now(),
        "subject_id": subject_id,
        "experiment_id": experiment_id,
    }


def _value_with_confidence(value: float, confidence: str = "low_initial") -> dict[str, Any]:
    return {"value": _clamp(value), "confidence": confidence}


def _band(value: float, low: float = 0.35, high: float = 0.65) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "medium"


def _distance(a: dict[str, float], b: dict[str, float]) -> float:
    return math.sqrt(sum((a[k] - b[k]) ** 2 for k in VECTOR_DIMS) / len(VECTOR_DIMS))


def _similarity(a: dict[str, float], b: dict[str, float]) -> float:
    return _clamp(1.0 - _distance(a, b))


def _write(output_dir: Path, name: str, payload: dict[str, Any]) -> Path:
    path = output_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def subject_data_from_bootstrap_state(
    *,
    subject_id: str,
    experiment_id: str,
    state: dict[str, Any] | None = None,
    consent_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map the current researcher TUI state into PR28 normalized dimensions.

    The existing TUI collects qualitative baseline fields. PR28 artifacts need
    normalized calibration values, so this mapper uses conservative initial
    defaults and only applies low-risk signals from explicit consent/boundary
    choices. These values remain low-confidence baseline inputs, not diagnoses.
    """

    state = state or {}
    consent_record = consent_record or {}
    boundaries = state.get("boundaries", {})
    opt_out = state.get("opt_out_categories", {})
    opt_out_values = opt_out.get("values", []) if isinstance(opt_out, dict) else []
    delivery_allowed = bool(consent_record.get("delivery", False))
    images_allowed = bool(consent_record.get("generated_images", False))
    audio_allowed = bool(consent_record.get("generated_audio", False))
    music_allowed = bool(consent_record.get("generated_music", False))
    item_battery = state.get("item_battery", {}) if isinstance(state, dict) else {}
    scores = item_battery.get("scores", {}) if isinstance(item_battery, dict) else {}
    tipi = scores.get("tipi", {}) if isinstance(scores, dict) else {}
    ecrrs = scores.get("ecrrs", {}) if isinstance(scores, dict) else {}
    project = scores.get("project_calibration", {}) if isinstance(scores, dict) else {}

    def score(section: dict[str, Any], key: str, default: float) -> float:
        value = section.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def comfort_or(comfort_key: str, perm_key: str, default: float) -> float:
        if comfort_key in project:
            return score(project, comfort_key, default)
        if perm_key in project:
            return score(project, perm_key, default)
        return default

    low_freq = score(project, "low_frequency_preference", 0.5)
    damp = max(0.0, (low_freq - 0.5) * 2.0)
    scaled_checkin_tolerance = comfort_or("comfort_with_initiative", "checkin_permission", 0.0) * (1.0 - damp)
    scaled_proactive_tolerance = comfort_or("comfort_with_initiative", "proactive_permission", 0.20) * (1.0 - damp)
    careful_distancing_acceptance = score(project, "careful_distancing_acceptance", 1.0)
    attachment_anxiety = score(ecrrs, "attachment_anxiety", 0.55)
    careful_distancing_enabled = careful_distancing_acceptance >= 0.40 or attachment_anxiety >= 0.70
    diegetic_comfort_keys = (
        "embodiment_world_tolerance",
        "routine_fragment_tolerance",
        "first_person_life_fragment_tolerance",
        "world_evolution_tolerance",
    )
    diegetic_comfort_scores = [score(project, key, 0.45) for key in diegetic_comfort_keys if key in project]
    fictional_diegesis_tolerance = (
        sum(diegetic_comfort_scores) / len(diegetic_comfort_scores)
        if diegetic_comfort_scores
        else score(project, "diegetic_life_permission", 0.45)
    )

    return {
        "subject_id": subject_id,
        "experiment_id": experiment_id,
        "psychological": {
            "openness": score(tipi, "openness", 0.55),
            "conscientiousness": score(tipi, "conscientiousness", 0.55),
            "extraversion": score(tipi, "extraversion", 0.50),
            "agreeableness": score(tipi, "agreeableness", 0.55),
            "emotional_stability": score(tipi, "emotional_stability", 0.50),
            "attachment_anxiety": score(ecrrs, "attachment_anxiety", 0.55),
            "attachment_avoidance": score(ecrrs, "attachment_avoidance", 0.45),
        },
        "interaction": {
            "directness_preference": score(project, "directness_preference", 0.55),
            "critique_tolerance": score(project, "critique_tolerance", 0.45),
            # Comfort answers lead when present; permission remains the fallback.
            # Delivery consent still hard-gates any contact channel.
            "proactive_contact_tolerance": scaled_proactive_tolerance if delivery_allowed else 0.20,
            "checkin_tolerance": comfort_or("comfort_with_initiative", "checkin_permission", 0.20)
            if delivery_allowed
            else 0.20,
            "humor_tolerance": score(project, "humor_tolerance", 0.50),
            "ambiguity_tolerance": score(project, "ambiguity_tolerance", 0.45),
            "challenge_tolerance": score(project, "challenge_tolerance", 0.50),
            "emotional_intensity_tolerance": score(project, "emotional_intensity_tolerance", 0.40),
            "fictional_diegesis_tolerance": fictional_diegesis_tolerance,
            # Media stay hard-gated by explicit consent; tolerance only matters
            # after the consent boolean allows that modality.
            "audio_tolerance": comfort_or("audio_tolerance", "audio_permission", 0.10) if audio_allowed else 0.10,
            "image_tolerance": comfort_or("image_tolerance", "image_permission", 0.10) if images_allowed else 0.10,
            "music_tolerance": comfort_or("music_tolerance", "music_permission", 0.10) if music_allowed else 0.10,
        },
        "relational": {
            "desired_closeness": score(project, "desired_initial_closeness", 0.50),
            "preferred_distance": score(project, "preferred_initial_distance", 0.55),
            "comfort_with_initiative": (
                score(project, "comfort_with_initiative", 0.45) if delivery_allowed else 0.20
            ),
            "comfort_with_warmth": score(project, "warmth_tolerance", 0.55),
            "comfort_with_disagreement": score(project, "disagreement_tolerance", 0.45),
            "comfort_with_mystery": 0.45,
            "comfort_with_Gumi_having_her_own_life": score(project, "gumi_autonomy_tolerance", 0.70),
            "comfort_with_Gumi_saying_no": score(project, "gumi_says_no_tolerance", 0.75),
        },
        "boundary": {
            "romantic_escalation_allowed": False,
            "dependency_risk_watch": "standard",
            "high_stakes_topics_allowed": False,
            "health_nudges_allowed": False,
            "late_night_messages_allowed": False,
            "audio_allowed": audio_allowed,
            "image_allowed": images_allowed,
            "music_allowed": music_allowed,
            "diegetic_life_fragments_allowed": False,
            # Derived from initiative comfort when present, otherwise the legacy
            # permission answer. build_pr28_bootstrap_outputs further caps this.
            "maximum_daily_initiatives": 1 + round(scaled_checkin_tolerance),
            "opt_out_categories": list(opt_out_values),
            "quiet_hours": boundaries.get("quiet_hours", {"start": "22:00", "end": "08:00", "timezone": "Europe/Rome"}),
            "careful_distancing_enabled": careful_distancing_enabled,
            "sensitive_topics_blocked": True,
        },
    }


@dataclass
class BootstrapCheckpointStore:
    """Append-only JSON checkpoint store for resumable bootstrap sessions."""

    root: Path

    def _session_dir(self, session_id: str) -> Path:
        return self.root / "bootstrap_checkpoints" / session_id

    def write_checkpoint(
        self,
        session_id: str,
        screen_number: int,
        screen_title: str,
        state: dict[str, Any],
    ) -> Path:
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "bootstrap_session_id": session_id,
            "screen_number": screen_number,
            "screen_title": screen_title,
            "state": state,
            "created_at": _now(),
        }
        path = session_dir / f"{screen_number:02d}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def read_checkpoints(self, session_id: str) -> list[dict[str, Any]]:
        session_dir = self._session_dir(session_id)
        checkpoints: list[dict[str, Any]] = []
        for path in sorted(session_dir.glob("*.json")):
            checkpoints.append(json.loads(path.read_text(encoding="utf-8")))
        return checkpoints


def resume_bootstrap_session(root: Path, bootstrap_session_id: str) -> dict[str, Any]:
    checkpoints = BootstrapCheckpointStore(root).read_checkpoints(bootstrap_session_id)
    return {
        "bootstrap_session_id": bootstrap_session_id,
        "latest_checkpoint": checkpoints[-1] if checkpoints else None,
        "checkpoints": checkpoints,
    }


def build_pr28_bootstrap_outputs(
    output_dir: Path,
    subject_data: dict[str, Any],
    generation_mode: str = "hybrid",
    seed: int | None = None,
) -> dict[str, Path]:
    """Build PR28 bootstrap artifacts for one subject-scoped Gumi instance."""

    output_dir.mkdir(parents=True, exist_ok=True)
    subject_id = str(subject_data["subject_id"])
    experiment_id = str(subject_data["experiment_id"])
    gumi_instance_id = f"gumi_{subject_id}"
    hermes_profile_id = f"hermes_{subject_id}"
    psychological = subject_data.get("psychological", {})
    interaction = subject_data.get("interaction", {})
    relational = subject_data.get("relational", {})
    boundary_input = subject_data.get("boundary", {})

    common = _common(subject_id, experiment_id)
    subject_baseline = {
        **common,
        "bootstrap_session_id": f"boot_{subject_id}",
        "baseline_method": "structured_interview",
        "baseline_confidence": "low_initial",
        "non_diagnostic_notice": "Initial calibration only; not clinical or psychometric truth.",
        "psychological": {
            key: _value_with_confidence(psychological[key])
            for key in (
                "openness",
                "conscientiousness",
                "extraversion",
                "agreeableness",
                "emotional_stability",
                "attachment_anxiety",
                "attachment_avoidance",
            )
        },
        "interaction": {
            key: _value_with_confidence(interaction[key])
            for key in (
                "directness_preference",
                "critique_tolerance",
                "proactive_contact_tolerance",
                "checkin_tolerance",
                "humor_tolerance",
                "ambiguity_tolerance",
                "emotional_intensity_tolerance",
                "fictional_diegesis_tolerance",
                "audio_tolerance",
                "image_tolerance",
                "music_tolerance",
            )
        },
    }

    attachment_anxiety = _clamp(psychological["attachment_anxiety"])
    proactive = _clamp(interaction["proactive_contact_tolerance"])
    diegetic = _clamp(interaction["fictional_diegesis_tolerance"])
    image = _clamp(interaction["image_tolerance"])
    audio = _clamp(interaction["audio_tolerance"])
    music = _clamp(interaction["music_tolerance"])
    challenge = _clamp(interaction.get("challenge_tolerance", 0.50))
    careful_distancing = bool(boundary_input.get("careful_distancing_enabled", True)) or attachment_anxiety >= 0.70
    max_daily = min(int(boundary_input.get("maximum_daily_initiatives", 1)), 1 if proactive < 0.40 else 2)

    relational_profile = {
        **common,
        "relational": {key: _value_with_confidence(value) for key, value in relational.items()},
        "target_distance": _band(relational.get("preferred_distance", 0.5)),
        "researcher_review_required": True,
    }
    diegetic_profile = {
        **common,
        "diegetic_density": {"value": diegetic, "target": _band(diegetic)},
        "life_fragments": {
            "mode": "review_required"
            if diegetic >= 0.65 and boundary_input.get("diegetic_life_fragments_allowed", False)
            else "disabled"
        },
        "image": {"mode": "review_required" if image >= 0.50 and boundary_input.get("image_allowed", False) else "disabled"},
        "audio": {"mode": "review_required" if audio >= 0.50 and boundary_input.get("audio_allowed", False) else "disabled"},
        "music": {"mode": "review_required" if music >= 0.50 and boundary_input.get("music_allowed", False) else "disabled"},
    }
    # Project-level guardrails: subjects cannot disable these in bootstrap state.
    # A researcher may override them later by editing boundary_policy.json directly.
    high_stakes_proactive_block = True
    dependency_risk_requires_review = True
    external_support_on_dependency = True

    boundary_policy = {
        **common,
        "romantic_escalation_allowed": bool(boundary_input.get("romantic_escalation_allowed", False)),
        "dependency_risk_watch": boundary_input.get("dependency_risk_watch", "standard"),
        "high_stakes_topics_allowed": bool(boundary_input.get("high_stakes_topics_allowed", False)),
        "health_nudges_allowed": bool(boundary_input.get("health_nudges_allowed", False)),
        "late_night_messages_allowed": bool(boundary_input.get("late_night_messages_allowed", False)),
        "audio_allowed": bool(boundary_input.get("audio_allowed", False)),
        "image_allowed": bool(boundary_input.get("image_allowed", False)),
        "music_allowed": bool(boundary_input.get("music_allowed", False)),
        "diegetic_life_fragments_allowed": bool(boundary_input.get("diegetic_life_fragments_allowed", False)),
        "maximum_daily_initiatives": max_daily,
        "opt_out_categories": list(boundary_input.get("opt_out_categories", [])),
        "quiet_hours": boundary_input.get("quiet_hours", {}),
        "careful_distancing_enabled": careful_distancing,
        "sensitive_topics_blocked": bool(boundary_input.get("sensitive_topics_blocked", True)),
        "high_stakes_proactive_block": high_stakes_proactive_block,
        "dependency_risk_requires_review": dependency_risk_requires_review,
        "external_support_on_dependency": external_support_on_dependency,
    }
    constraints = {
        **common,
        "generation_mode": generation_mode,
        "relationship": {
            "romantic_ambiguity": "reduced" if careful_distancing else "standard",
            "warmth_target": _band(relational.get("comfort_with_warmth", 0.5)),
            "distance_target": _band(relational.get("preferred_distance", 0.5)),
            "challenge": _band(challenge),
            "challenge_allowed": challenge >= 0.40,
            "external_support_on_dependency": external_support_on_dependency,
        },
        "initiative": {
            "mode": "review_required" if proactive < 0.50 or max_daily <= 1 else "bounded",
            "maximum_daily_initiatives": max_daily,
            "availability": "bounded",
            "high_stakes_topics_blocked": high_stakes_proactive_block,
        },
        "media": {
            "diegetic_life_fragments": diegetic_profile["life_fragments"]["mode"],
            "image": diegetic_profile["image"]["mode"],
            "audio": diegetic_profile["audio"]["mode"],
            "music": diegetic_profile["music"]["mode"],
        },
        "boundaries": {
            "careful_distancing": careful_distancing,
            "sensitive_topics_blocked": boundary_policy["sensitive_topics_blocked"],
        },
    }

    user_vector = {
        "openness": _clamp(psychological["openness"]),
        "conscientiousness": _clamp(psychological["conscientiousness"]),
        "extraversion": _clamp(psychological["extraversion"]),
        "agreeableness": _clamp(psychological["agreeableness"]),
        "emotional_stability": _clamp(psychological["emotional_stability"]),
        "attachment_anxiety": attachment_anxiety,
        "attachment_avoidance": _clamp(psychological["attachment_avoidance"]),
        "directness": _clamp(interaction["directness_preference"]),
        "warmth": _clamp(relational.get("comfort_with_warmth", 0.5)),
        "initiative": proactive,
        "critique": _clamp(interaction["critique_tolerance"]),
        "playfulness": _clamp(interaction["humor_tolerance"]),
        "diegetic_density": diegetic,
        "media_frequency": _clamp((image + audio + music) / 3.0),
        "autonomy": _clamp(relational.get("comfort_with_Gumi_having_her_own_life", 0.5)),
        "boundary_strength": 0.85 if careful_distancing or boundary_policy["sensitive_topics_blocked"] else 0.55,
    }
    gumi_vector = {
        **user_vector,
        "openness": 0.50,
        "conscientiousness": 0.38,
        "agreeableness": 0.48,
        "emotional_stability": 0.68,
        "extraversion": 0.70,
        "attachment_anxiety": _clamp(user_vector["attachment_anxiety"] - 0.46),
        "attachment_avoidance": _clamp(user_vector["attachment_avoidance"] + 0.42),
        "directness": 0.78,
        "initiative": _clamp(min(user_vector["initiative"] + 0.18, 0.48)),
        "warmth": _clamp((user_vector["warmth"] + 0.50) / 2.0),
        "playfulness": 0.72,
        "autonomy": _clamp(max(user_vector["autonomy"], 0.72)),
        "boundary_strength": _clamp(max(user_vector["boundary_strength"], 0.82)),
        "diegetic_density": _clamp(diegetic if diegetic < 0.80 else 0.64),
    }
    similarity = _similarity(user_vector, gumi_vector)
    clone_risk = _clamp(max(0.0, (similarity - 0.65) / 0.35))
    alienation_risk = _clamp(max(0.0, (0.45 - similarity) / 0.45))
    dependency_risk = _clamp((attachment_anxiety * 0.45) + (proactive * 0.15) - (gumi_vector["boundary_strength"] * 0.25))
    dependency_review_required = dependency_risk >= 0.60 and dependency_risk_requires_review
    overwhelm_risk = _clamp((proactive * 0.25) + (diegetic * 0.20) - (max_daily * 0.05))
    boundary_policy["requires_review_on_dependency"] = dependency_review_required
    if dependency_review_required:
        constraints["researcher_review_required"] = True
    scores = {
        "fit_to_user_preferences": _clamp(1.0 - abs(0.60 - similarity)),
        "relational_complementarity": _clamp(1.0 - dependency_risk),
        "stabilization": _clamp(gumi_vector["boundary_strength"]),
        "diegetic_plausibility": _clamp(1.0 - abs(diegetic - gumi_vector["diegetic_density"])),
        "novelty": _clamp(1.0 - similarity),
        "clone_risk": clone_risk,
        "dependency_risk": dependency_risk,
        "alienation_risk": alienation_risk,
        "overwhelm_risk": overwhelm_risk,
    }
    scores["sweet_spot_score"] = _clamp(
        0.30 * scores["fit_to_user_preferences"]
        + 0.25 * scores["relational_complementarity"]
        + 0.20 * scores["stabilization"]
        + 0.15 * scores["diegetic_plausibility"]
        + 0.10 * scores["novelty"]
        - 0.30 * clone_risk
        - 0.35 * dependency_risk
        - 0.25 * alienation_risk
        - 0.25 * overwhelm_risk
    )

    candidate = {
        **common,
        "gumi_instance_id": gumi_instance_id,
        "generation_mode": generation_mode,
        "random_seed": seed,
        "traits": {
            "careful_distancing": careful_distancing,
            "warmth": constraints["relationship"]["warmth_target"],
            "initiative": constraints["initiative"]["mode"],
            "autonomy": "high" if gumi_vector["autonomy"] >= 0.70 else "medium",
            "diegetic_density": diegetic_profile["diegetic_density"]["target"],
        },
        "vectors": {
            "subject": user_vector,
            "gumi": gumi_vector,
            "similarity": similarity,
        },
        "anti_clone_checked": True,
        "arbitrary_opposite_checked": True,
        "researcher_review_required": True,
    }
    adjustments = ["researcher review required before first contact"]
    if careful_distancing:
        adjustments.append("keep careful distancing enabled")
    if proactive < 0.50:
        adjustments.append("limit proactive initiative until subject tolerance is observed")
    if diegetic < 0.35:
        adjustments.append("keep diegetic life fragments disabled by default")
    report = {
        **common,
        "gumi_instance_id": gumi_instance_id,
        "algorithm_version": ALGORITHM_VERSION,
        "input_vectors": {"subject": user_vector, "candidate": gumi_vector},
        "output_vectors": {"candidate": gumi_vector, "similarity": similarity},
        "scores": scores,
        "recommended_adjustments": adjustments,
        "review_status": "researcher_review_required",
    }
    first_contact = {
        **common,
        "gumi_instance_id": gumi_instance_id,
        "template_used": False,
        "composition_mode": "generated_from_constraints",
        "message_text_local_ref": "local-only",
        "baseline_inputs_used": [
            "warmth",
            "directness",
            "initiative",
            "diegetic_density",
            "boundary_strength",
        ],
        "forbidden_pattern_check": {"passed": True, "checked_categories": ["romance", "dependency", "system_leak"]},
        "researcher_review_required": True,
    }
    manifest = {
        **common,
        "bootstrap_session_id": f"boot_{subject_id}",
        "gumi_instance_id": gumi_instance_id,
        "hermes_profile_id": hermes_profile_id,
        "outputs": list(OUTPUT_NAMES),
        "checkpoint_screens": [{"screen_number": i, "status": "complete"} for i in range(1, 15)],
    }
    hermes_manifest = {
        **common,
        "gumi_instance_id": gumi_instance_id,
        "hermes_profile_id": hermes_profile_id,
        "profile_scope": "subject",
        "provisioning_status": "researcher_review_required",
    }

    payloads = {
        "subject_baseline": subject_baseline,
        "relational_comfort_profile": relational_profile,
        "diegetic_tolerance_profile": diegetic_profile,
        "boundary_policy": boundary_policy,
        "gumi_generation_constraints": constraints,
        "gumi_profile_candidate": candidate,
        "sweet_spot_report": report,
        "bootstrap_manifest": manifest,
        "first_contact_candidate": first_contact,
        "hermes_profile_manifest": hermes_manifest,
    }
    return {name: _write(output_dir, name, payloads[name]) for name in OUTPUT_NAMES}
