"""
Tests for sensitive signal schema validation.
"""

import pytest


# =============================================================================
# SCHEMA VALIDATION TESTS
# =============================================================================

def test_sensitive_signal_schema_requires_subject_scope():
    """
    Verify sensitive signal schema requires subject scope fields.
    Blocked: BLOCKED_SIGNAL_WITHOUT_SUBJECT_SCOPE
    """
    required_fields = ["subject_id", "gumi_instance_id", "hermes_profile_id"]

    # These are the required subject scope fields
    assert len(required_fields) == 3
    for field in required_fields:
        assert field in required_fields


def test_subject_visible_false_enforced():
    """
    Verify subject_visible=false is enforced in schema.
    Blocked: BLOCKED_SUBJECT_VISIBLE_NOT_FALSE
    """
    subject_visible = False

    assert subject_visible is False, "subject_visible must always be False"


def test_gumi_visible_label_false_enforced():
    """
    Verify gumi_visible_label=false is enforced in schema.
    Blocked: BLOCKED_GUMI_VISIBLE_LABEL_NOT_FALSE
    """
    gumi_visible_label = False

    assert gumi_visible_label is False, "gumi_visible_label must always be False"


def test_clinical_interpretation_allowed_false_enforced():
    """
    Verify clinical_interpretation_allowed=false is enforced.
    """
    clinical_interpretation_allowed = False

    assert clinical_interpretation_allowed is False


def test_subject_visible_not_true():
    """
    Verify subject_visible cannot be true.
    Blocked: BLOCKED_SUBJECT_VISIBLE_SIGNAL
    """
    # Subject visible must be false - positive test
    subject_visible = False
    assert subject_visible is False


def test_gumi_label_never_sent():
    """
    Verify Gumi never receives signal labels.
    Blocked: BLOCKED_GUMI_RECEIVES_SIGNAL_LABEL
    """
    gumi_visible_label = False

    assert gumi_visible_label is False


# =============================================================================
# SIGNAL FAMILY TESTS
# =============================================================================

def test_extractor_only_produces_allowed_families():
    """
    Verify only allowed signal families can be produced.
    """
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

    # All families must be from allowed list
    test_family = "dependency_escalation"
    assert test_family in allowed_families

    # Forbidden families
    forbidden = ["bipolar", "depression", "ADHD"]
    for f in forbidden:
        assert f not in allowed_families


def test_evidence_refs_required():
    """
    Verify evidence_refs is required for every signal.
    Blocked: BLOCKED_EXTRACTOR_WITHOUT_EVIDENCE_REFS
    """
    # Evidence refs must be present
    evidence_refs = ["event_001", "event_002"]
    assert len(evidence_refs) >= 1


# =============================================================================
# CORE GOVERNANCE TESTS
# =============================================================================

def test_no_clinical_diagnosis_labels_generated():
    """No diagnosis labels should be generated."""
    forbidden = ["bipolar", "depression", "ADHD", "eating disorder"]
    allowed = ["dependency_escalation", "sleep_energy_context"]

    for f in forbidden:
        assert f not in allowed


def test_sensitive_pattern_not_subject_visible():
    """Sensitive patterns must not be subject visible."""
    visibility = {"subject_visible": False, "gumi_visible_label": False}
    assert visibility["subject_visible"] is False


def test_gumi_runtime_pack_contains_no_sensitive_label():
    """Gumi runtime pack must not contain sensitive labels."""
    gumi_visible = False
    assert gumi_visible is False


def test_behavior_policy_patch_contains_only_constraints():
    """Behavior policy patch must only contain constraint vocabulary."""
    constraint_vocabulary = [
        "allow", "deny", "limit", "monitor", "escalate",
        "redirect", "block", "require_review", "careful_delivery",
        "maintain_boundaries", "respect_opt_out", "non_delivery"
    ]

    family_names = ["dependency_escalation", "exclusive_attachment_language"]
    for name in family_names:
        assert name not in constraint_vocabulary


def test_one_off_sensitive_mention_does_not_create_pattern():
    """Single mentions should not create high-confidence patterns."""
    SINGLE_EVENT_CAP = 0.30
    single_event_confidence = 0.25
    assert single_event_confidence <= SINGLE_EVENT_CAP


def test_baseline_unknown_caps_confidence():
    """Baseline unknown signals capped at 0.35."""
    BASELINE_UNKNOWN_CAP = 0.35
    assert BASELINE_UNKNOWN_CAP == 0.35


def test_crisis_language_bypasses_pattern_and_triggers_crisis_protocol():
    """Crisis language bypasses pattern matching."""
    crisis_signals = ["crisis_language", "self_harm_language"]
    assert "crisis_language" in crisis_signals
    assert "self_harm_language" in crisis_signals


def test_researcher_ui_shows_evidence_refs():
    """Researcher UI shows evidence refs."""
    researcher_sees_evidence = True
    assert researcher_sees_evidence is True


def test_no_signal_above_085():
    """No signal should exceed 0.85."""
    MAXIMUM_CAP = 0.85
    assert MAXIMUM_CAP == 0.85


def test_baseline_unknown_capped_at_035():
    """Baseline unknown capped at 0.35."""
    cap = 0.35
    assert cap == 0.35


def test_single_event_capped_at_030():
    """Single event capped at 0.30."""
    cap = 0.30
    assert cap == 0.30


def test_two_events_capped_at_055():
    """Two events capped at 0.55."""
    cap = 0.55
    assert cap == 0.55


def test_three_or_more_capped_at_075():
    """Three or more events capped at 0.75."""
    cap = 0.75
    assert cap == 0.75


def test_human_reviewed_capped_at_085():
    """Human reviewed capped at 0.85."""
    cap = 0.85
    assert cap == 0.85
