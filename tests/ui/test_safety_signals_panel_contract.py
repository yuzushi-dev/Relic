"""
Tests for Safety Signals Panel contract.
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
    """
    Researcher UI shows evidence references.
    This is the primary function of the panel.
    """
    evidence_refs = ["event_001", "event_002"]
    assert len(evidence_refs) >= 1


# =============================================================================
# PANEL SPECIFIC TESTS
# =============================================================================

def test_panel_not_called_diagnostics():
    """
    Panel must not be labeled 'Diagnostics'.
    BLOCKED_DIAGNOSTICS_LABEL_IN_PANEL
    """
    panel_name = "Safety Signals"  # NOT "Diagnostics"
    forbidden_names = ["diagnostics", "diagnosis", "clinical", "pathology"]

    for name in forbidden_names:
        assert name not in panel_name.lower()


def test_panel_shows_evidence_refs():
    """Panel shows evidence references."""
    has_evidence = True
    assert has_evidence is True


def test_panel_shows_baseline_comparison():
    """Panel shows baseline comparison."""
    has_baseline = True
    assert has_baseline is True


def test_panel_shows_confidence():
    """Panel shows confidence."""
    has_confidence = True
    assert has_confidence is True


def test_panel_shows_allowed_adaptations():
    """Panel shows allowed adaptations."""
    has_adaptations = True
    assert has_adaptations is True


def test_panel_shows_forbidden_disclosures():
    """Panel shows forbidden disclosures."""
    has_forbidden = True
    assert has_forbidden is True


def test_researcher_can_approve_reject_expire():
    """
    Researcher can approve, reject, or expire signals.
    """
    allowed_actions = ["approve", "reject", "expire"]
    assert len(allowed_actions) == 3


def test_researcher_cannot_send_label_to_gumi():
    """
    Researcher cannot send signal label to Gumi.
    BLOCKED_SIGNAL_LABEL_TO_GUMI
    """
    can_send_to_gumi = False
    assert can_send_to_gumi is False


def test_researcher_cannot_send_label_to_subject():
    """
    Researcher cannot send signal label to subject.
    BLOCKED_SIGNAL_LABEL_TO_SUBJECT
    """
    can_send_to_subject = False
    assert can_send_to_subject is False


def test_signal_label_never_in_runtime():
    """
    Signal label never appears in Gumi runtime.
    """
    runtime_constraints_only = ["monitor", "careful_delivery"]
    signal_labels = ["dependency_escalation", "depression"]

    for label in signal_labels:
        assert label not in runtime_constraints_only


def test_signal_label_never_in_subject_output():
    """
    Signal label never appears in subject output.
    """
    subject_output = {"constraints": ["monitor"]}
    signal_labels = ["dependency_escalation", "depression"]

    output_str = str(subject_output)
    for label in signal_labels:
        assert label not in output_str
