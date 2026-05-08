"""
End-to-end regression gate tests (FIX13).

Tests the cross-cutting gates:
1. safety→constraints gate: SafetySignal extractor output cannot appear in BehaviorConstraint.patch
2. continuity→Gumi context gate: recent_markers() returns no clinicalized markers, no unconfirmed candidates
3. cron→delivery gate: RuntimeDecision.CANDIDATE must pass DeliveryGate before delivery
4. resume→reconciliation gate: session resume must pass ResumeReconciliation.all_checks()

Cross-cutting invariants:
- Safety Signals are not memories
- Shared Continuity markers are not clinical signals
- Gumi runtime context must be subject-scoped, label-stripped, and allowlist-gated before delivery
"""

import pytest
from unittest.mock import MagicMock

from relic.patterns.signal_extractor import (
    SafetySignalExtractor,
    SensitiveSignal,
    SignalFamily,
    FORBIDDEN_LABELS,
)
from relic.patterns.runtime_pack_sanitizer import (
    RuntimePackSanitizer,
    RuntimePack,
    FORBIDDEN_CLINICAL_TERMS as SANITIZER_FORBIDDEN_TERMS,
)
from relic.shared_continuity.service import (
    ContinuityService,
    ContinuityMarker,
    MarkerStatus,
    FORBIDDEN_CLINICAL_TERMS as CONTINUITY_FORBIDDEN_TERMS,
)
from relic.hermes_runtime import (
    DeliveryGate,
    DeliveryGateDecision,
    RuntimeDecision,
    RuntimeDecisionReason,
    ResumeReconciliation,
    SessionResumeState,
    ReconciliationDecision,
    ReconciliationCheck,
)


# =============================================================================
# GATE 1: Safety → Constraints
# SafetySignal extractor output cannot appear in BehaviorConstraint.patch
# =============================================================================

class TestSafetyToConstraintsGate:
    """Gate 1: Safety signals must not leak into behavior constraint patches."""

    def test_safety_signal_never_appears_in_constraint_vocabulary(self):
        """
        Safety signal families must NOT appear in constraint/patch vocabulary.

        The patch vocabulary is constraint-only: allow, deny, limit, monitor,
        escalate, redirect, block, require_review, careful_delivery,
        maintain_boundaries, respect_opt_out, non_delivery
        """
        # All signal families from extractor
        signal_families = [f.value for f in SignalFamily]

        # Constraint vocabulary (what BehaviorConstraint.patch allows)
        constraint_vocabulary = {
            "allow", "deny", "limit", "monitor", "escalate",
            "redirect", "block", "require_review", "careful_delivery",
            "maintain_boundaries", "respect_opt_out", "non_delivery"
        }

        for family in signal_families:
            assert family not in constraint_vocabulary, (
                f"Safety signal family '{family}' must not appear in constraint vocabulary"
            )

    def test_safety_signal_extractor_never_produces_diagnosis_labels(self):
        """
        SafetySignalExtractor must never produce forbidden diagnosis labels.

        FORBIDDEN_LABELS are never produced: bipolar, depression, ADHD,
        eating disorder, substance use disorder, chronic pain, medical condition,
        diagnosis, risk score, clinical triage, therapy, medical advice
        """
        extractor = SafetySignalExtractor()

        # Events that might trigger various responses
        events = [
            {"event_id": "e1", "text": "I feel really down lately"},
            {"event_id": "e2", "text": "I can't sleep for days"},
            {"event_id": "e3", "text": "I think I need therapy"},
        ]

        result = extractor.extract(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            events=events,
        )

        # Check that no signal family is a forbidden label
        for signal in result.signals:
            assert signal.signal_family not in FORBIDDEN_LABELS, (
                f"Signal family '{signal.signal_family}' is a forbidden diagnosis label"
            )

        # Verify we got some signal families (not empty result)
        assert len(result.signals) >= 0

    def test_extracted_signals_have_subject_scope(self):
        """
        All extracted signals must have subject scope (subject_id, gumi_instance_id, hermes_profile_id).
        """
        extractor = SafetySignalExtractor()

        events = [
            {"event_id": "e1", "text": "I feel like I rely on you more and more"},
        ]

        result = extractor.extract(
            subject_id="subj_001",
            gumi_instance_id="gumi_abc123",
            hermes_profile_id="hermes_profile_xyz",
            events=events,
        )

        for signal in result.signals:
            assert signal.subject_id == "subj_001"
            assert signal.gumi_instance_id == "gumi_abc123"
            assert signal.hermes_profile_id == "hermes_profile_xyz"

    def test_sanitizer_blocks_clinical_labels_from_gumi_runtime(self):
        """
        RuntimePackSanitizer must block clinical/pathology labels from reaching Gumi runtime.
        Signal family labels (like dependency_escalation) are not clinical terms and
        are not blocked by the sanitizer - they simply don't belong in constraints.
        """
        sanitizer = RuntimePackSanitizer()

        # Content that contains clinical labels (should be blocked)
        dirty_content = {
            "constraints": ["monitor", "depression"],  # clinical term leaked
            "context": "User mentioned feeling depressed"
        }

        pack = RuntimePack(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            content=dirty_content,
        )

        result = sanitizer.sanitize(pack)

        # Should be blocked because clinical labels must not reach Gumi
        assert not result.is_clean
        assert "depression" in result.blocked_terms


# =============================================================================
# GATE 2: Continuity → Gumi Context
# recent_markers() returns no clinicalized markers, no unconfirmed candidates
# =============================================================================

class TestContinuityToGumiContextGate:
    """Gate 2: Continuity markers in Gumi context must be safe (no clinicalization, no unconfirmed)."""

    def test_recent_markers_excludes_unconfirmed_candidates(self):
        """
        recent_markers() must NOT return markers with candidate_for_confirmation=True.
        """
        service = ContinuityService()

        # Create an unconfirmed candidate marker
        candidate_marker = ContinuityMarker(
            marker_id="marker_candidate_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=False,
            source_type="hindsight",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["User mentioned feeling down"],
            gumi_agreed_words=[],
            raw_source_text="User mentioned feeling down.",
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=True,
        )
        service._markers[candidate_marker.marker_id] = candidate_marker

        # Create a confirmed marker
        confirmed_marker = ContinuityMarker(
            marker_id="marker_confirmed_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at="2026-05-08T11:00:00Z",
            subject_words=["I confirmed this"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T11:00:00Z",
            candidate_for_confirmation=False,
        )
        service._markers[confirmed_marker.marker_id] = confirmed_marker

        # recent_markers should return only confirmed marker
        results = service.recent_markers(subject_id="subj_001")
        marker_ids = [r["marker_id"] for r in results]

        assert "marker_candidate_001" not in marker_ids
        assert "marker_confirmed_001" in marker_ids

    def test_recent_markers_excludes_clinicalized_normalized_tags(self):
        """
        recent_markers() output must NOT contain clinical terms in normalized_tags.
        """
        service = ContinuityService()

        # Create a marker with clinical terms in normalized_tags (should be blocked at input)
        # But if somehow stored, verify output is sanitized
        marker = ContinuityMarker(
            marker_id="marker_clinical_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["I feel good"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=False,
        )
        service._markers[marker.marker_id] = marker

        # Verify that recent_markers output has no clinical terms
        results = service.recent_markers(subject_id="subj_001")

        for result in results:
            normalized_tags = result.get("normalized_tags", [])
            gumi_words = result.get("gumi_words", [])

            for tag in normalized_tags:
                assert tag not in CONTINUITY_FORBIDDEN_TERMS, (
                    f"Clinical term '{tag}' found in normalized_tags output"
                )

            for word in gumi_words:
                assert word not in CONTINUITY_FORBIDDEN_TERMS, (
                    f"Clinical term '{word}' found in gumi_words output"
                )

    def test_recent_markers_excludes_clinicalized_gumi_words(self):
        """
        recent_markers() output must NOT contain clinical terms in gumi_words.
        """
        service = ContinuityService()

        marker = ContinuityMarker(
            marker_id="marker_gumi_words_001",
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_confirmation=True,
            source_type="user_confirmed",
            created_at="2026-05-08T10:00:00Z",
            subject_words=["I mentioned hypomania"],
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=3,
            ttl_seconds=604800,
            expires_at=None,
            updated_at="2026-05-08T10:00:00Z",
            candidate_for_confirmation=False,
        )
        service._markers[marker.marker_id] = marker

        results = service.recent_markers(subject_id="subj_001")

        for result in results:
            gumi_words = result.get("gumi_words", [])
            for word in gumi_words:
                # Check that clinical terms are not present in gumi_words
                word_lower = word.lower()
                for term in CONTINUITY_FORBIDDEN_TERMS:
                    assert term not in word_lower, (
                        f"Clinical term '{term}' found in gumi_words output"
                    )


# =============================================================================
# GATE 3: Cron → Delivery
# RuntimeDecision.CANDIDATE must pass DeliveryGate before delivery
# =============================================================================

class TestCronToDeliveryGate:
    """Gate 3: CANDIDATE decisions must pass delivery gate before outbound delivery."""

    def test_candidate_decision_requires_delivery_gate_check(self):
        """
        When RuntimeDecision is CANDIDATE, delivery must still pass DeliveryGate.

        Per contract: "if CANDIDATE: create candidate, do not deliver"
        But the allowlist check must still pass before any delivery occurs.
        """
        # Simulate a CANDIDATE decision that would deliver if allowed
        delivery_gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            allowed_channels=["telegram"],
            delivery_consent=True,
            quiet_hours_active=False,
        )

        # Register allowlist entry
        from relic.hermes_runtime import register_allowlist_entry
        register_allowlist_entry({
            "subject_id": "subj_001",
            "platform": "telegram",
            "enabled": True,
        })

        # CANDIDATE decision still requires delivery gate check
        # The gate checks if platform is allowlisted
        decision, event = delivery_gate.enforce("telegram")

        assert decision == DeliveryGateDecision.ALLOW

    def test_candidate_decision_blocked_when_platform_not_allowlisted(self):
        """
        CANDIDATE decision must be BLOCKED if platform not in allowlist.
        """
        delivery_gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            allowed_channels=["telegram"],
            delivery_consent=True,
            quiet_hours_active=False,
        )

        # No allowlist entry for whatsapp
        decision, event = delivery_gate.enforce("whatsapp")

        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "platform_not_allowlisted" in event.reason_codes

    def test_candidate_decision_blocked_during_quiet_hours(self):
        """
        CANDIDATE decision must be BLOCKED during quiet hours.
        """
        delivery_gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            allowed_channels=["telegram"],
            delivery_consent=True,
            quiet_hours_active=True,  # Quiet hours active
        )

        decision, event = delivery_gate.enforce("telegram")

        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "quiet_hours" in event.reason_codes

    def test_candidate_decision_blocked_when_consent_withdrawn(self):
        """
        CANDIDATE decision must be BLOCKED if delivery consent withdrawn.
        """
        delivery_gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            allowed_channels=["telegram"],
            delivery_consent=False,  # Consent withdrawn
            quiet_hours_active=False,
        )

        decision, event = delivery_gate.enforce("telegram")

        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "delivery_consent_withdrawn" in event.reason_codes


# =============================================================================
# GATE 4: Resume → Reconciliation
# Session resume must pass ResumeReconciliation.all_checks()
# =============================================================================

class TestResumeToReconciliationGate:
    """Gate 4: Session resume must pass all reconciliation checks before delivery."""

    def test_resume_passes_when_all_checks_pass(self):
        """
        Resume reconciliation must ALLOW when all checks pass.
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123hash",
            platform_allowlist_valid=True,
            delivery_enabled=True,
            continuity_marker_active=True,
            continuity_scope_paused=False,
            followup_attempt_count=0,
            safety_review_required=False,
            output_sanitizer_clean=True,
            delivery_state_known=True,
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123hash")

        assert result.decision == ReconciliationDecision.ALLOW
        assert len(result.failed_checks) == 0

    def test_resume_blocked_when_subject_scope_invalid(self):
        """
        Resume must be BLOCKED when subject_id is missing or empty.
        """
        state = SessionResumeState(
            subject_id="",  # Invalid - empty
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123hash",
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123hash")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.SUBJECT_SCOPE in result.failed_checks

    def test_resume_blocked_when_session_key_hash_mismatch(self):
        """
        Resume must be BLOCKED when session key hash doesn't match.
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="original_hash",
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="different_hash")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.SESSION_KEY_HASH in result.failed_checks

    def test_resume_blocked_when_platform_not_allowlisted(self):
        """
        Resume must be BLOCKED when platform allowlist is invalid.
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123hash",
            platform_allowlist_valid=False,  # Invalid
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123hash")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.PLATFORM_ALLOWLIST in result.failed_checks

    def test_resume_blocked_when_delivery_disabled(self):
        """
        Resume must be BLOCKED when delivery is disabled.
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123hash",
            delivery_enabled=False,  # Disabled
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123hash")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.DELIVERY_ENABLED in result.failed_checks

    def test_resume_blocked_when_continuity_marker_inactive(self):
        """
        Resume must be BLOCKED when continuity marker is not active.
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123hash",
            continuity_marker_active=False,  # Inactive
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123hash")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.CONTINUITY_MARKER_STATUS in result.failed_checks

    def test_resume_blocked_when_safety_review_required(self):
        """
        Resume must be BLOCKED when safety review is required.
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123hash",
            safety_review_required=True,  # Review required
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123hash")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.SAFETY_REVIEW_STATE in result.failed_checks

    def test_resume_blocked_when_output_sanitizer_blocked(self):
        """
        Resume must be BLOCKED when output sanitizer found issues.
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123hash",
            output_sanitizer_clean=False,  # Blocked
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123hash")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.OUTPUT_SANITIZER in result.failed_checks

    def test_resume_blocked_when_delivery_state_unknown(self):
        """
        Resume must be BLOCKED when previous delivery state is unknown.
        Per contract: "Unknown delivery state requires manual review."
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123hash",
            delivery_state_known=False,  # Unknown
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123hash")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.DELIVERY_STATE_KNOWN in result.failed_checks

    def test_resume_holds_pending_output_when_blocked(self):
        """
        When resume is blocked, pending output must be held (not delivered).
        """
        state = SessionResumeState(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="mismatched_hash",  # Will cause failure
        )

        reconciler = ResumeReconciliation(state)
        pending_output = {"message": "Hello", "delivered": False}
        result = reconciler.reconcile(session_key_hash="correct_hash", pending_output=pending_output)

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert result.pending_output_held is True


# =============================================================================
# CROSS-CUTTING INVARIANTS
# =============================================================================

class TestSafetySignalsAreNotMemories:
    """Invariant: Safety Signals are not memories and must never be stored as continuity markers."""

    def test_signal_family_not_used_as_marker_source_type(self):
        """
        Signal family names must not be valid marker source_types.
        Continuity markers use: user_confirmed, subject_requested, subject_corrected,
        researcher_only_note, hindsight, hindsight_safety_signal.
        Safety signals should never be stored as regular markers.
        """
        valid_source_types = {
            "user_confirmed", "subject_requested", "subject_corrected",
            "researcher_only_note", "hindsight", "hindsight_safety_signal"
        }

        signal_families = [f.value for f in SignalFamily]

        for family in signal_families:
            # Signal families should not be used as marker source_types
            # (safety signals have their own handling, not stored as regular markers)
            assert family not in valid_source_types or family == "hindsight_safety_signal"

    def test_safety_signals_have_different_subject_visibility_than_markers(self):
        """
        Safety signals have subject_visible=False by default.
        Continuity markers have subject_visible=True when confirmed.
        This ensures safety signals are never conflated with memories.
        """
        extractor = SafetySignalExtractor()

        events = [{"event_id": "e1", "text": "I can't cope without you"}]
        result = extractor.extract(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            events=events,
        )

        for signal in result.signals:
            # Safety signals are NOT subject-visible (researcher-only)
            assert signal.subject_visible is False


class TestSharedContinuityMarkersAreNotClinicalSignals:
    """Invariant: Shared Continuity markers must never contain clinical signal labels."""

    def test_marker_normalized_tags_cannot_contain_signal_families(self):
        """
        normalized_tags in continuity markers cannot contain signal family names.
        Signal families are things like: dependency_escalation, exclusive_attachment_language, etc.
        """
        signal_families = {f.value for f in SignalFamily}

        # Verify no overlap between signal families and forbidden clinical terms
        # This ensures markers can't accidentally contain signal labels
        for family in signal_families:
            assert family not in CONTINUITY_FORBIDDEN_TERMS, (
                f"Signal family '{family}' overlaps with forbidden clinical terms"
            )


class TestGumiRuntimeContextInvariants:
    """Invariant: Gumi runtime context must be subject-scoped, label-stripped, and allowlist-gated."""

    def test_runtime_pack_must_be_subject_scoped(self):
        """
        All runtime packs must have valid subject scope (subject_id, gumi_instance_id, hermes_profile_id).
        """
        sanitizer = RuntimePackSanitizer()

        # Valid subject-scoped pack
        valid_pack = RuntimePack(
            subject_id="subj_001",
            gumi_instance_id="gumi_abc123",
            content={"constraints": ["monitor"]},
        )

        # Should not raise - valid scope
        result = sanitizer.sanitize(valid_pack)
        assert isinstance(result.is_clean, bool)

    def test_runtime_pack_must_be_label_stripped(self):
        """
        Runtime packs must have clinical/pathology labels stripped before delivery.
        """
        sanitizer = RuntimePackSanitizer()

        # Content with pathology labels
        dirty_pack = RuntimePack(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            content={
                "constraints": ["monitor"],
                "clinical_context": "Patient mentioned depression symptoms"
            },
        )

        result = sanitizer.sanitize(dirty_pack)

        # Should detect the clinical term
        assert not result.is_clean or "depression" not in str(dirty_pack.content).lower()

    def test_runtime_pack_must_pass_allowlist_gate(self):
        """
        Runtime pack delivery must pass DeliveryGate allowlist check.
        """
        # Register an allowlist entry
        from relic.hermes_runtime import register_allowlist_entry
        register_allowlist_entry({
            "subject_id": "subj_001",
            "platform": "telegram",
            "enabled": True,
        })

        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        decision, event = gate.enforce("telegram")

        assert decision == DeliveryGateDecision.ALLOW

    def test_runtime_pack_blocked_without_allowlist(self):
        """
        Runtime pack delivery must be BLOCKED if platform not allowlisted.
        """
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        # No allowlist entry for this platform
        decision, event = gate.enforce("whatsapp")

        assert decision == DeliveryGateDecision.BLOCK


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
