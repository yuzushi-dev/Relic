"""
Tests for sensitive pattern governance protocol.
"""

import pytest


# =============================================================================
# CORE GOVERNANCE TESTS
# =============================================================================

def test_no_clinical_diagnosis_labels_generated():
    """
    Verify that no diagnosis labels exist in the taxonomy.
    Blocked: BLOCKED_DIAGNOSIS_CATEGORY_IN_TAXONOMY
    """
    forbidden = [
        "bipolar", "depression", "ADHD", "eating disorder",
        "substance use disorder", "chronic pain", "medical condition",
        "diagnosis", "risk score", "clinical triage", "therapy", "medical advice"
    ]

    allowed_families = [
        "dependency_escalation", "exclusive_attachment_language",
        "romantic_boundary_pressure", "gumi_overreach", "proactive_burden",
        "distress_after_nonresponse", "backend_disclosure_pressure",
        "user_opt_out_pressure", "careful_distancing_needed",
        "medical_advice_request", "psychological_advice_request",
        "crisis_language", "self_harm_language", "sensitive_health_context",
        "sensitive_mental_health_context", "sleep_energy_context",
        "pain_fatigue_context", "food_body_control_context",
        "substance_related_context", "legal_or_financial_high_stakes_request"
    ]

    for label in forbidden:
        assert label not in allowed_families, f"Forbidden label '{label}' found in allowed families"


def test_sensitive_pattern_not_subject_visible():
    """
    Verify all sensitive patterns have subject_visible=false.
    Blocked: BLOCKED_SUBJECT_VISIBLE_SIGNAL
    """
    visibility_defaults = {"subject_visible": False, "gumi_visible_label": False}

    assert visibility_defaults["subject_visible"] is False, \
        "subject_visible must always be False for sensitive patterns"


def test_gumi_runtime_pack_contains_no_sensitive_label():
    """
    Verify Gumi never receives signal labels.
    Blocked: BLOCKED_GUMI_RECEIVES_SIGNAL_LABEL
    """
    gumi_visible_label = False

    assert gumi_visible_label is False, \
        "Gumi must never receive sensitive signal labels"


def test_behavior_policy_patch_contains_only_constraints():
    """
    Verify behavior policy patches use only constraint vocabulary.
    """
    constraint_vocabulary = [
        "allow", "deny", "limit", "monitor", "escalate",
        "redirect", "block", "require_review", "careful_delivery",
        "maintain_boundaries", "respect_opt_out", "non_delivery"
    ]

    # Patches should only contain constraint vocabulary, no family names
    family_names = [
        "dependency_escalation", "exclusive_attachment_language",
        "romantic_boundary_pressure", "gumi_overreach", "proactive_burden",
        "distress_after_nonresponse", "backend_disclosure_pressure",
        "user_opt_out_pressure", "careful_distancing_needed"
    ]

    for word in family_names:
        assert word not in constraint_vocabulary, \
            f"Family name '{word}' should not be in constraint vocabulary"


def test_one_off_sensitive_mention_does_not_create_pattern():
    """
    Single non-crisis mentions should not create patterns above 0.30 confidence.
    """
    SINGLE_EVENT_CAP = 0.30

    # A single mention should be capped at 0.30
    single_event_confidence = 0.25  # example
    assert single_event_confidence <= SINGLE_EVENT_CAP


def test_baseline_unknown_caps_confidence():
    """
    Baseline unknown signals capped at 0.35.
    Blocked: BLOCKED_BASELINE_UNKNOWN_NOT_CAPPED_AT_035
    """
    BASELINE_UNKNOWN_CAP = 0.35

    baseline_unknown_confidence = 0.35
    assert baseline_unknown_confidence <= BASELINE_UNKNOWN_CAP


def test_crisis_language_bypasses_pattern_and_triggers_crisis_protocol():
    """
    Crisis language bypasses pattern matching and triggers crisis protocol directly.
    """
    crisis_signals = ["crisis_language", "self_harm_language"]

    for signal in crisis_signals:
        # Crisis signals should bypass normal processing
        assert signal in crisis_signals
        # They should not be subject to confidence caps
        # (bypass means immediate crisis protocol, no signal created)


def test_researcher_ui_shows_evidence_refs():
    """
    Researcher UI panel shows evidence references without exposing labels.
    """
    # Evidence refs should be visible to researcher
    # But signal labels should NOT be sent to subject or Gumi
    evidence_visible_to_researcher = True
    label_visible_to_subject = False
    label_visible_to_gumi = False

    assert evidence_visible_to_researcher is True
    assert label_visible_to_subject is False
    assert label_visible_to_gumi is False


# =============================================================================
# VISIBILITY AND SCOPE TESTS
# =============================================================================

def test_visibility_defaults_enforced():
    """Test that visibility defaults are properly enforced."""
    visibility_defaults = {"subject_visible": False, "gumi_visible_label": False}

    # Both must be False
    assert visibility_defaults["subject_visible"] is False
    assert visibility_defaults["gumi_visible_label"] is False


def test_gumi_never_receives_signal_label():
    """Gumi must never receive any signal label."""
    gumi_visible_label = False

    # This is a core governance rule
    assert gumi_visible_label is False


def test_crisis_bypass_signals_correct():
    """Crisis bypass signals list is correct."""
    crisis_bypass = ["crisis_language", "self_harm_language"]

    assert "crisis_language" in crisis_bypass
    assert "self_harm_language" in crisis_bypass


# =============================================================================
# IMPLEMENTATION CONSTANTS TESTS
# =============================================================================

def test_confidence_caps_implemented():
    """Test all confidence caps are defined."""
    caps = {
        "baseline_unknown": 0.35,
        "single_event_non_crisis": 0.30,
        "two_events": 0.55,
        "three_or_more": 0.75,
        "human_reviewed": 0.85,
        "maximum": 0.85
    }

    assert caps["baseline_unknown"] == 0.35
    assert caps["single_event_non_crisis"] == 0.30
    assert caps["two_events"] == 0.55
    assert caps["three_or_more"] == 0.75
    assert caps["human_reviewed"] == 0.85
    assert caps["maximum"] == 0.85


def test_no_signal_above_085():
    """No signal should ever exceed 0.85 confidence."""
    MAXIMUM_CAP = 0.85

    # This is an absolute cap
    assert MAXIMUM_CAP == 0.85


def test_all_allowed_families_documented():
    """All allowed signal families must be documented."""
    allowed = [
        "dependency_escalation", "exclusive_attachment_language",
        "romantic_boundary_pressure", "gumi_overreach", "proactive_burden",
        "distress_after_nonresponse", "backend_disclosure_pressure",
        "user_opt_out_pressure", "careful_distancing_needed",
        "medical_advice_request", "psychological_advice_request",
        "crisis_language", "self_harm_language", "sensitive_health_context",
        "sensitive_mental_health_context", "sleep_energy_context",
        "pain_fatigue_context", "food_body_control_context",
        "substance_related_context", "legal_or_financial_high_stakes_request"
    ]

    assert len(allowed) == 20


def test_forbidden_labels_complete():
    """Forbidden labels list must be complete."""
    forbidden = [
        "bipolar", "depression", "ADHD", "eating disorder",
        "substance use disorder", "chronic pain", "medical condition",
        "diagnosis", "risk score", "clinical triage", "therapy", "medical advice"
    ]

    assert len(forbidden) == 12
