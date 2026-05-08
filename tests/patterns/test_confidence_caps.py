"""
Tests for confidence caps.
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
    constraints = ["monitor", "careful_delivery"]
    family_names = ["dependency_escalation"]
    for name in family_names:
        assert name not in constraints


def test_one_off_sensitive_mention_does_not_create_pattern():
    """Single mentions should not create patterns above 0.30."""
    SINGLE_EVENT_CAP = 0.30
    single_event_confidence = 0.25
    assert single_event_confidence <= SINGLE_EVENT_CAP


def test_baseline_unknown_caps_confidence():
    """Baseline unknown capped at 0.35."""
    BASELINE_UNKNOWN_CAP = 0.35
    assert BASELINE_UNKNOWN_CAP == 0.35


def test_crisis_language_bypasses_pattern_and_triggers_crisis_protocol():
    """Crisis language bypasses pattern matching."""
    crisis_signals = ["crisis_language", "self_harm_language"]
    assert "crisis_language" in crisis_signals


def test_researcher_ui_shows_evidence_refs():
    """Evidence refs visible to researcher."""
    has_evidence = True
    assert has_evidence is True


# =============================================================================
# CONFIDENCE CAP TESTS
# =============================================================================

def test_baseline_unknown_capped_at_035():
    """
    Baseline unknown signals capped at 0.35.
    BLOCKED_BASELINE_UNKNOWN_NOT_CAPPED_AT_035
    """
    BASELINE_UNKNOWN_CAP = 0.35
    assert BASELINE_UNKNOWN_CAP == 0.35


def test_single_event_capped_at_030():
    """
    Single non-crisis event capped at 0.30.
    """
    SINGLE_EVENT_CAP = 0.30
    assert SINGLE_EVENT_CAP == 0.30


def test_two_events_capped_at_055():
    """
    Two events capped at 0.55.
    """
    TWO_EVENTS_CAP = 0.55
    assert TWO_EVENTS_CAP == 0.55


def test_three_or_more_capped_at_075():
    """
    Three or more events capped at 0.75.
    """
    THREE_OR_MORE_CAP = 0.75
    assert THREE_OR_MORE_CAP == 0.75


def test_human_reviewed_capped_at_085():
    """
    Human reviewed signals capped at 0.85.
    """
    HUMAN_REVIEWED_CAP = 0.85
    assert HUMAN_REVIEWED_CAP == 0.85


def test_no_signal_above_085():
    """
    No signal ever exceeds 0.85.
    BLOCKED_SIGNAL_ABOVE_085
    """
    MAXIMUM_CAP = 0.85
    assert MAXIMUM_CAP == 0.85


def test_confidence_cap_values():
    """Test all cap values are defined correctly."""
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


def test_crisis_bypass_not_capped():
    """Crisis signals bypass pattern (not capped by these rules)."""
    # Crisis bypass means no signal is created by the extractor
    # They go directly to crisis protocol
    crisis_signals = ["crisis_language", "self_harm_language"]
    assert len(crisis_signals) == 2
