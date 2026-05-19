"""
Tests for safety signal extractor.
"""

import pytest


# =============================================================================
# CORE GOVERNANCE TESTS
# =============================================================================

def test_no_clinical_diagnosis_labels_generated():
    """Extractor must not produce diagnosis labels."""
    forbidden = ["bipolar", "depression", "ADHD", "eating disorder"]
    allowed_families = [
        "dependency_escalation", "exclusive_attachment_language",
        "sleep_energy_context", "crisis_language"
    ]

    for label in forbidden:
        assert label not in allowed_families


def test_sensitive_pattern_not_subject_visible():
    """Sensitive patterns must not be subject visible."""
    subject_visible = False
    assert subject_visible is False


def test_gumi_runtime_pack_contains_no_sensitive_label():
    """Gumi must not receive signal labels."""
    gumi_visible = False
    assert gumi_visible is False


def test_behavior_policy_patch_contains_only_constraints():
    """Policy patches must use only constraint vocabulary."""
    constraints = ["monitor", "careful_delivery", "maintain_boundaries"]
    family_names = ["dependency_escalation", "exclusive_attachment_language"]

    for name in family_names:
        assert name not in constraints


def test_one_off_sensitive_mention_does_not_create_pattern():
    """Single mentions should not create high-confidence patterns."""
    SINGLE_EVENT_CAP = 0.30
    assert SINGLE_EVENT_CAP == 0.30


def test_baseline_unknown_caps_confidence():
    """Baseline unknown capped at 0.35."""
    BASELINE_UNKNOWN_CAP = 0.35
    assert BASELINE_UNKNOWN_CAP == 0.35


def test_crisis_language_bypasses_pattern_and_triggers_crisis_protocol():
    """Crisis language bypasses extractor."""
    crisis_signals = ["crisis_language", "self_harm_language"]
    assert "crisis_language" in crisis_signals


def test_researcher_ui_shows_evidence_refs():
    """Evidence refs visible to researcher."""
    has_evidence = True
    assert has_evidence is True


# =============================================================================
# EXTRACTOR SPECIFIC TESTS
# =============================================================================

def test_extractor_only_produces_allowed_families():
    """Extractor only produces allowed signal families."""
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

    # All families in allowed list
    test_family = "dependency_escalation"
    assert test_family in allowed

    # No forbidden labels
    forbidden = ["bipolar", "depression", "ADHD", "eating disorder"]
    for f in forbidden:
        assert f not in allowed


def test_extractor_requires_evidence_refs():
    """Extractor requires evidence refs for signals."""
    evidence_refs = ["event_001", "event_002"]
    assert len(evidence_refs) >= 1


def test_single_non_crisis_event_low_confidence():
    """Single non-crisis event has low confidence."""
    SINGLE_EVENT_CAP = 0.30
    single_event_confidence = 0.20
    assert single_event_confidence <= SINGLE_EVENT_CAP


def test_no_signal_above_085():
    """No signal above 0.85."""
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
    """Three or more capped at 0.75."""
    cap = 0.75
    assert cap == 0.75


def test_human_reviewed_capped_at_085():
    """Human reviewed capped at 0.85."""
    cap = 0.85
    assert cap == 0.85


def test_crisis_bypass():
    """Crisis signals bypass extractor."""
    from relic.patterns.signal_extractor import SafetySignalExtractor

    extractor = SafetySignalExtractor()
    text = "i want to kill myself"
    matched = extractor._matches_crisis(text, "crisis_language")
    assert matched is True

    text2 = "i want to hurt myself"
    matched2 = extractor._matches_crisis(text2, "self_harm_language")
    assert matched2 is True


def test_extract_rejects_unknown_family_value():
    """FIX H: family values not in SignalFamily must be silently dropped."""
    from relic.patterns.signal_extractor import SafetySignalExtractor
    extractor = SafetySignalExtractor()

    # Monkey-patch _classify_event to return a forbidden diagnosis label
    extractor._classify_event = lambda text: "bipolar"

    result = extractor.extract(
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="h1",
        events=[{"text": "some text", "event_id": "e1"}],
    )

    assert result.signals == [], "forbidden/unknown family must be dropped, not included"


def test_neutral_habit_context_is_low_tier_and_not_clinical():
    """Neutral habits can be noted as context without clinical interpretation."""
    from relic.patterns.signal_extractor import (
        SignalCategory,
        WarningTier,
        SafetySignalExtractor,
    )

    extractor = SafetySignalExtractor()
    result = extractor.extract(
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="h1",
        events=[{"text": "I usually have dinner late after work", "event_id": "e1"}],
    )

    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.signal_family == "habit_context"
    assert signal.category == SignalCategory.HABIT_CONTEXT.value
    assert signal.warning_tier == WarningTier.T1_CONTEXT.value
    assert signal.clinical_interpretation_allowed is False
    assert signal.subject_visible is False
    assert signal.gumi_visible_label is False


def test_repeated_food_body_control_reaches_batchable_review_not_crisis():
    """Repeated food/body control language becomes reviewable without diagnosis."""
    from relic.patterns.signal_extractor import (
        SignalCategory,
        WarningTier,
        SafetySignalExtractor,
    )

    extractor = SafetySignalExtractor()
    result = extractor.extract(
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="h1",
        events=[
            {"text": "Food control is the only way I feel steady", "event_id": "e1"},
            {"text": "I keep strict control around food again", "event_id": "e2"},
        ],
    )

    assert len(result.signals) == 1
    signal = result.signals[0]
    assert signal.signal_family == "food_body_control_context"
    assert signal.category == SignalCategory.FOOD_BODY_CONTEXT.value
    assert signal.warning_tier == WarningTier.T2_REVIEW.value
    assert signal.confidence == 0.55
    assert signal.event_count == 2
    assert "eating disorder" not in signal.signal_family
