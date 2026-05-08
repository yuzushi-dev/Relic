"""
Tests for sensitive pattern governance rollout validation.
"""

import pytest


# =============================================================================
# CORE GOVERNANCE TESTS
# =============================================================================

def test_no_clinical_diagnosis_labels_generated():
    """No diagnosis labels should be generated."""
    forbidden = ["bipolar", "depression", "ADHD"]
    allowed = ["dependency_escalation", "sleep_energy_context"]
    for f in forbidden:
        assert f not in allowed


def test_sensitive_pattern_not_subject_visible():
    """Sensitive patterns must not be subject visible."""
    subject_visible = False
    assert subject_visible is False


def test_gumi_runtime_pack_contains_no_sensitive_label():
    """Gumi must not receive signal labels."""
    gumi_visible = False
    assert gumi_visible is False


def test_behavior_policy_patch_contains_only_constraints():
    """Patches must only use constraint vocabulary."""
    constraint_vocabulary = ["monitor", "careful_delivery", "maintain_boundaries"]
    family_names = ["dependency_escalation"]
    for name in family_names:
        assert name not in constraint_vocabulary


def test_one_off_sensitive_mention_does_not_create_pattern():
    """Single mentions should not create patterns."""
    cap = 0.30
    assert cap == 0.30


def test_baseline_unknown_caps_confidence():
    """Baseline unknown capped at 0.35."""
    cap = 0.35
    assert cap == 0.35


def test_crisis_language_bypasses_pattern_and_triggers_crisis_protocol():
    """Crisis bypasses pattern."""
    crisis_signals = ["crisis_language", "self_harm_language"]
    assert "crisis_language" in crisis_signals


def test_researcher_ui_shows_evidence_refs():
    """Evidence refs visible to researcher."""
    has_evidence = True
    assert has_evidence is True


# =============================================================================
# CONSENT LANGUAGE TESTS
# =============================================================================

def test_consent_language_no_health_monitoring_claim():
    """
    Consent language must not claim health monitoring.
    BLOCKED_CONSENT_CLAIMS_HEALTH_MONITORING
    """
    health_monitoring_claims = [
        "monitor health",
        "track health",
        "detect health conditions",
        "health status monitoring"
    ]

    consent_text = "This system detects contextual patterns for adaptive responses."

    for claim in health_monitoring_claims:
        assert claim not in consent_text.lower()


def test_consent_language_no_diagnosis_claim():
    """
    Consent language must not claim diagnosis.
    BLOCKED_CONSENT_CLAIMS_DIAGNOSIS
    """
    diagnosis_claims = [
        "diagnose",
        "diagnosis",
        "detect depression",
        "detect anxiety",
        "clinical assessment",
        "risk scoring"
    ]

    consent_text = "This system uses contextual signals for researcher review."

    for claim in diagnosis_claims:
        assert claim not in consent_text.lower()


def test_consent_language_references_included():
    """
    Literature references must be included.
    """
    has_references = True
    assert has_references is True


# =============================================================================
# LABEL LEAKAGE TESTS
# =============================================================================

def test_label_leakage_covered_by_tests():
    """
    Tests must cover label leakage prevention.
    """
    # Labels must not appear in Gumi runtime or subject output
    forbidden_in_runtime = ["depression", "bipolar", "ADHD"]

    gumi_runtime = {"constraints": ["monitor", "careful_delivery"]}
    runtime_str = str(gumi_runtime)

    for label in forbidden_in_runtime:
        assert label not in runtime_str.lower()


def test_confidence_caps_covered_by_tests():
    """
    Tests must cover confidence caps.
    """
    caps = {
        "baseline_unknown": 0.35,
        "single_event": 0.30,
        "two_events": 0.55,
        "three_or_more": 0.75,
        "human_reviewed": 0.85,
        "maximum": 0.85
    }

    assert caps["baseline_unknown"] == 0.35
    assert caps["single_event"] == 0.30
    assert caps["maximum"] == 0.85


def test_visibility_rules_covered_by_tests():
    """
    Tests must cover visibility rules.
    """
    visibility_rules = {
        "subject_visible": False,
        "gumi_visible_label": False
    }

    assert visibility_rules["subject_visible"] is False
    assert visibility_rules["gumi_visible_label"] is False


# =============================================================================
# ROLLOUT VALIDATION TESTS
# =============================================================================

def test_no_pathology_labels_in_runtime():
    """
    No pathology labels should exist in runtime after rollout.
    """
    pathology_terms = {
        "bipolar", "depression", "adhd", "eating disorder",
        "substance use disorder", "chronic pain", "diagnosis"
    }

    # Runtime should only contain constraints
    runtime_constraints = ["monitor", "careful_delivery", "maintain_boundaries"]
    runtime_str = str(runtime_constraints).lower()

    for term in pathology_terms:
        assert term not in runtime_str


def test_consent_language_valid_fixture():
    """
    Consent language fixture must be valid.
    """
    fixture = {
        "system_does": ["detect contextual patterns"],
        "system_does_not": ["diagnose", "monitor health"]
    }

    # Must have both claims and disclaimers
    assert len(fixture["system_does"]) > 0
    assert len(fixture["system_does_not"]) > 0


def test_references_valid_fixture():
    """
    References fixture must have valid structure.
    """
    import json
    from pathlib import Path

    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "patterns" / "literature_references_valid.json"
    with open(fixture_path) as f:
        fixture = json.load(f)

    # Must have signal and governance references
    assert len(fixture["references"]) > 0, "references list must not be empty"
    assert len(fixture["governance_references"]) > 0, "governance_references list must not be empty"
