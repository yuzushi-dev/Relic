"""Tests for the PR25 Bootstrap TUI item battery contract."""
from __future__ import annotations

from relic.profile._bootstrap_steps.item_battery import (
    BOOTSTRAP_ITEM_REGISTRY,
    score_ecrrs,
    score_tipi,
)


def test_every_item_has_required_registry_metadata() -> None:
    required = {
        "item_id",
        "screen",
        "canonical_text",
        "display_text_it",
        "response_scale",
        "construct",
        "source_class",
        "source_name",
        "source_citation",
        "reverse_scored",
        "required",
        "used_for",
    }
    for item in BOOTSTRAP_ITEM_REGISTRY:
        assert required <= set(item)
        assert item["source_class"] in {
            "validated_instrument",
            "adapted_validated_construct",
            "project_derived_calibration",
            "project_derived_safety_gate",
            "researcher_configuration",
        }
        assert item["response_scale"]
        assert item["source_citation"]


def test_validated_items_are_not_mixed_with_project_items() -> None:
    for item in BOOTSTRAP_ITEM_REGISTRY:
        if item["source_name"] in {"TIPI", "ECR-RS"}:
            assert item["source_class"] == "validated_instrument"
        if item["source_name"].startswith("Relic/Gumi"):
            assert item["source_class"].startswith("project_derived")


def test_tipi_reverse_scoring_items_2_4_6_8_10() -> None:
    reversed_ids = {
        item["item_id"]
        for item in BOOTSTRAP_ITEM_REGISTRY
        if item["source_name"] == "TIPI" and item["reverse_scored"]
    }
    assert reversed_ids == {"TIPI_002", "TIPI_004", "TIPI_006", "TIPI_008", "TIPI_010"}


def test_tipi_trait_averages_and_normalization() -> None:
    responses = {
        "TIPI_001": 7,
        "TIPI_002": 1,
        "TIPI_003": 7,
        "TIPI_004": 1,
        "TIPI_005": 7,
        "TIPI_006": 1,
        "TIPI_007": 7,
        "TIPI_008": 1,
        "TIPI_009": 7,
        "TIPI_010": 1,
    }
    assert score_tipi(responses) == {
        "extraversion": 1.0,
        "agreeableness": 1.0,
        "conscientiousness": 1.0,
        "emotional_stability": 1.0,
        "openness": 1.0,
    }


def test_ecrrs_scoring_contract() -> None:
    responses = {
        "ECRRS_001": 1,
        "ECRRS_002": 1,
        "ECRRS_003": 1,
        "ECRRS_004": 1,
        "ECRRS_005": 7,
        "ECRRS_006": 7,
        "ECRRS_007": 7,
        "ECRRS_008": 7,
        "ECRRS_009": 7,
    }
    assert score_ecrrs(responses) == {
        "attachment_avoidance": 1.0,
        "attachment_anxiety": 1.0,
    }


def test_desired_initial_closeness_derived_from_rel010() -> None:
    # IOS_001 removed; desired_initial_closeness derived from REL_010 (distance_7, inverse)
    from relic.profile._bootstrap_steps.item_battery import score_item_battery
    from io import StringIO
    responses = {"REL_010": 2}  # distance=2 → closeness=6
    battery = {"responses": responses}
    # Build minimal responses for all required items
    all_items = {item["item_id"]: 4 for item in BOOTSTRAP_ITEM_REGISTRY}
    all_items["REL_010"] = 2
    scores = score_item_battery(all_items)
    closeness = scores["project_calibration"]["desired_initial_closeness"]
    assert closeness > 0.5  # REL_010=2 (low distance) → high closeness


def test_required_addendum_sections_are_present() -> None:
    screens = {item["screen"] for item in BOOTSTRAP_ITEM_REGISTRY}
    assert {
        "big_five",
        "attachment",
        "interaction_preferences",
        "relational_comfort",
        "diegetic_tolerance",
        "proactivity_permissions",
        "safety_boundary_gates",
    } <= screens


def test_safety_gate_defaults_match_contract() -> None:
    defaults = {
        item["item_id"]: item["default_response"]
        for item in BOOTSTRAP_ITEM_REGISTRY
        if item["screen"] == "safety_boundary_gates"
    }
    assert defaults == {
        "SAFE_001": 0,
        "SAFE_002": 0,
        "SAFE_003": 0,
        "SAFE_004": 0,
        "SAFE_005": 1,
        "SAFE_006": 1,
        "SAFE_007": 1,
        "SAFE_008": 0,
        "SAFE_009": 0,
        "SAFE_010": 1,
    }


def test_proactivity_permissions_contract() -> None:
    proactivity_items = [
        item for item in BOOTSTRAP_ITEM_REGISTRY if item["screen"] == "proactivity_permissions"
    ]

    assert [item["item_id"] for item in proactivity_items] == [
        "PRO_001",
        "PRO_002",
        "PRO_003",
        "PRO_004",
        "PRO_005",
        "PRO_006",
        "PRO_007",
        "PRO_009",
        "PRO_010",
    ]
    assert {item["construct"] for item in proactivity_items} == {
        "checkin_permission",
        "followup_permission",
        "proactive_permission",
        "image_permission",
        "audio_permission",
        "music_permission",
        "diegetic_life_permission",
        "elicitation_permission",
        "no_reply_acceptance",
    }
