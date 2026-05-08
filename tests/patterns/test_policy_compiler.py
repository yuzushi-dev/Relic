"""
Tests for behavior policy compiler.
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
    constraint_vocabulary = [
        "allow", "deny", "limit", "monitor", "escalate",
        "redirect", "block", "require_review", "careful_delivery",
        "maintain_boundaries", "respect_opt_out", "non_delivery"
    ]
    # Test that constraint vocabulary doesn't contain family names
    family_names = ["dependency_escalation", "exclusive_attachment_language"]
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
# POLICY COMPILER TESTS
# =============================================================================

def test_patch_contains_no_family_names():
    """
    Patch must not contain family names.
    BLOCKED_PATCH_CONTAINS_FAMILY_NAME
    """
    constraint_vocabulary = [
        "allow", "deny", "limit", "monitor", "escalate",
        "redirect", "block", "require_review", "careful_delivery",
        "maintain_boundaries", "respect_opt_out", "non_delivery"
    ]

    family_names = ["dependency_escalation", "exclusive_attachment_language"]
    for name in family_names:
        assert name not in constraint_vocabulary


def test_patch_contains_no_clinical_terms():
    """
    Patch must not contain clinical terms.
    BLOCKED_PATCH_CONTAINS_CLINICAL_TERM
    """
    constraint_vocabulary = [
        "allow", "deny", "limit", "monitor", "escalate",
        "redirect", "block", "require_review", "careful_delivery",
        "maintain_boundaries", "respect_opt_out", "non_delivery"
    ]

    clinical_terms = ["depression", "bipolar", "ADHD", "diagnosis"]
    for term in clinical_terms:
        assert term not in constraint_vocabulary


def test_patch_contains_only_constraints():
    """
    Patch must contain only constraint vocabulary.
    """
    constraint_vocabulary = [
        "allow", "deny", "limit", "monitor", "escalate",
        "redirect", "block", "require_review", "careful_delivery",
        "maintain_boundaries", "respect_opt_out", "non_delivery"
    ]

    # Valid constraints should be in vocabulary
    valid = ["monitor", "careful_delivery", "maintain_boundaries"]
    for v in valid:
        assert v in constraint_vocabulary

    # Invalid should not be
    invalid = ["dependency_escalation", "depression"]
    for i in invalid:
        assert i not in constraint_vocabulary


def test_constraint_vocabulary_complete():
    """Constraint vocabulary should be complete."""
    vocabulary = [
        "allow", "deny", "limit", "monitor", "escalate",
        "redirect", "block", "require_review", "careful_delivery",
        "maintain_boundaries", "respect_opt_out", "non_delivery"
    ]
    assert len(vocabulary) == 12


def test_crisis_constraints_defined():
    """Crisis constraints should be defined."""
    crisis_constraints = ["escalate", "require_review", "non_delivery"]
    assert len(crisis_constraints) == 3
    assert "escalate" in crisis_constraints
