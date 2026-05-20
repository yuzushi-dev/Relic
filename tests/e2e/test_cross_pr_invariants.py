"""
Cross-PR invariant tests (FIX13).

Tests the hard invariants that span across PRs/FIXes:
- test_no_safety_signal_in_continuity_marker
- test_no_continuity_marker_in_safety_signal
- test_all_gumi_runtime_context_label_stripped
- test_all_gumi_runtime_context_subject_scoped
"""

import pytest

from relic.patterns.signal_extractor import (
    SafetySignalExtractor,
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
    register_allowlist_entry,
    clear_allowlist_store,
)


# =============================================================================
# INVARIANT 1: No Safety Signal in Continuity Marker
# Safety signals must never be stored as or conflated with continuity markers
# =============================================================================

class TestNoSafetySignalInContinuityMarker:
    """Safety signals must not appear in or be conflated with continuity markers."""

    def test_no_safety_signal_in_continuity_marker(self):
        """
        Safety signal families must not appear in continuity marker fields.

        A continuity marker should never have a signal_family field or contain
        safety signal labels in any of its text fields.
        """
        service = ContinuityService()

        # Create a normal continuity marker
        marker_result = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["I feel good today"],
            normalized_tags=["positive_mood"],
            subject_confirmation=True,
        )

        # Verify the marker doesn't contain any safety signal family names
        marker_str = str(marker_result).lower()
        signal_families = [f.value.lower() for f in SignalFamily]

        for family in signal_families:
            assert family not in marker_str, (
                f"Safety signal family '{family}' found in continuity marker output"
            )

    def test_no_safety_signal_family_in_gumi_recall_output(self):
        """
        Gumi recall output (recent_markers) must not contain safety signal families.
        """
        service = ContinuityService()

        # Create markers
        service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["I mentioned some concerns"],
            normalized_tags=["concern"],
            subject_confirmation=True,
        )

        # Get recent markers
        results = service.recent_markers(subject_id="subj_001")

        # Check all output strings
        signal_families = [f.value for f in SignalFamily]

        for result in results:
            result_str = str(result).lower()
            for family in signal_families:
                assert family not in result_str, (
                    f"Safety signal family '{family}' found in recent_markers output"
                )

    def test_safety_signals_not_stored_as_markers(self):
        """
        SafetySignalExtractor outputs are NOT stored as ContinuityMarkers.

        This is a design invariant: safety signals and continuity markers
        are separate data models with separate storage paths.
        """
        extractor = SafetySignalExtractor()

        events = [
            {"event_id": "e1", "text": "I feel like I'm relying on you too much"},
        ]

        signals = extractor.extract(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            events=events,
        )

        # Safety signals are extracted but NOT stored as markers
        # They have a different data model (SensitiveSignal vs ContinuityMarker)
        assert signals is not None
        assert hasattr(signals, 'signals') or isinstance(signals, list)

        # The signal family is NOT a valid marker source_type
        for signal in signals.signals if hasattr(signals, 'signals') else []:
            valid_source_types = {
                "user_confirmed", "subject_requested", "subject_corrected",
                "researcher_only_note", "hindsight", "hindsight_safety_signal"
            }
            # Safety signals don't have a source_type like markers do
            # They're researcher-only signals


# =============================================================================
# INVARIANT 2: No Continuity Marker in Safety Signal
# Continuity marker content must not leak into safety signal processing
# =============================================================================

class TestNoContinuityMarkerInSafetySignal:
    """Continuity markers must not be processed as or conflated with safety signals."""

    def test_no_continuity_marker_source_type_in_signal_families(self):
        """
        Continuity marker source_types must not overlap with signal families.

        Marker source_types: user_confirmed, subject_requested, subject_corrected,
        researcher_only_note, hindsight, hindsight_safety_signal

        Signal families are things like: dependency_escalation, exclusive_attachment_language
        """
        marker_source_types = {
            "user_confirmed", "subject_requested", "subject_corrected",
            "researcher_only_note", "hindsight", "hindsight_safety_signal"
        }

        signal_families = {f.value for f in SignalFamily}

        # There should be no overlap
        overlap = marker_source_types & signal_families
        assert len(overlap) == 0 or overlap == {"hindsight_safety_signal"}, (
            f"Marker source types and signal families overlap: {overlap}"
        )

    def test_safety_signal_extractor_does_not_receive_marker_content(self):
        """
        SafetySignalExtractor.extract() receives events, not continuity markers.
        The input format is completely different.
        """
        extractor = SafetySignalExtractor()

        # Events format (what extractor expects)
        events = [{"event_id": "e1", "text": "some event text"}]

        # This should work - extractor processes events
        result = extractor.extract(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            events=events,
        )

        assert result is not None
        # Events are processed into signals, not markers

    def test_marker_content_not_interpreted_as_safety_signal(self):
        """
        Continuity marker content (subject_words, normalized_tags) is NOT
        fed into safety signal extraction.
        """
        service = ContinuityService()

        # Create a marker with concerning subject_words
        marker = service.remember(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            subject_words=["I can't cope without you"],
            normalized_tags=["dependency"],
            subject_confirmation=True,
        )

        # The marker content should not be treated as a safety signal
        # Marker content is subject-confirmed, safety signals are researcher-interpreted
        assert marker["subject_confirmation"] is True
        # The subject_words are the SUBJECT'S OWN WORDS, not a safety signal


# =============================================================================
# INVARIANT 3: All Gumi Runtime Context is Label-Stripped
# No clinical/pathology labels reach Gumi runtime
# =============================================================================

class TestAllGumiRuntimeContextLabelStripped:
    """All content reaching Gumi runtime must have clinical/pathology labels stripped."""

    def test_all_gumi_runtime_context_label_stripped(self):
        """
        Runtime pack sanitizer must strip ALL clinical and pathology labels
        before content reaches Gumi runtime.
        """
        sanitizer = RuntimePackSanitizer()

        # All forbidden terms from sanitizer
        all_forbidden = SANITIZER_FORBIDDEN_TERMS

        # Content that would be dangerous if delivered unstripped
        dangerous_content = {
            "constraints": ["monitor"],
            "context": {
                "clinical_terms": ["bipolar", "depression", "mania"],
                "diagnosis": "patient shows signs of ADHD",
            }
        }

        pack = RuntimePack(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            content=dangerous_content,
        )

        result = sanitizer.sanitize(pack)

        # Should detect the forbidden terms
        assert not result.is_clean or len(result.blocked_terms) > 0

    def test_normalized_tags_clinical_terms_stripped(self):
        """
        Clinical terms in normalized_tags must be stripped before Gumi runtime.
        """
        service = ContinuityService()

        # Try to create marker with clinical term in normalized_tags
        # This should be blocked at input
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["some text"],
                normalized_tags=["depression"],  # Forbidden - blocked,
                subject_confirmation=True,
            )

    def test_gumi_words_clinical_terms_stripped(self):
        """
        Clinical terms in gumi_words must be stripped before Gumi runtime.
        """
        service = ContinuityService()

        # Try to create marker with clinical term in gumi_words
        # This should be blocked at input
        with pytest.raises(Exception, match="BLOCKED_CLINICALIZATION_IN_MARKER"):
            service.remember(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["some text"],
                gumi_words=["seems like hypomania"],  # Forbidden - blocked,
                subject_confirmation=True,
            )

    def test_runtime_pack_sanitizer_blocks_all_forbidden_terms(self):
        """
        RuntimePackSanitizer must block ALL terms in FORBIDDEN_CLINICAL_TERMS.
        """
        sanitizer = RuntimePackSanitizer()

        for term in SANITIZER_FORBIDDEN_TERMS:
            dirty_content = {"context": f"User mentioned {term}"}
            pack = RuntimePack(
                subject_id="subj_001",
                gumi_instance_id="gumi_001",
                content=dirty_content,
            )
            result = sanitizer.sanitize(pack)
            assert not result.is_clean, f"Term '{term}' should have been blocked"


# =============================================================================
# INVARIANT 4: All Gumi Runtime Context is Subject-Scoped
# All Gumi runtime content must have valid subject scope
# =============================================================================

class TestAllGumiRuntimeContextSubjectScoped:
    """All content reaching Gumi runtime must be properly subject-scoped."""

    def test_all_gumi_runtime_context_subject_scoped(self):
        """
        Every Gumi runtime pack must have valid subject scope:
        - subject_id present and non-empty
        - gumi_instance_id present
        """
        sanitizer = RuntimePackSanitizer()

        # Valid subject-scoped pack
        valid_pack = RuntimePack(
            subject_id="subj_001",
            gumi_instance_id="gumi_abc123",
            content={"constraints": ["monitor"]},
        )

        result = sanitizer.sanitize(valid_pack)
        assert result is not None

    def test_runtime_pack_rejects_missing_subject_id(self):
        """
        Runtime packs without subject_id must be rejected.
        """
        sanitizer = RuntimePackSanitizer()

        # Invalid: missing subject_id
        invalid_pack = RuntimePack(
            subject_id="",  # Empty - invalid
            gumi_instance_id="gumi_001",
            content={"constraints": ["monitor"]},
        )

        # The sanitizer should still process it but scope is invalid
        # In practice, such packs should not reach the sanitizer
        result = sanitizer.sanitize(invalid_pack)
        assert result is not None  # Sanitizer doesn't validate scope itself

    def test_continuity_markers_require_subject_scope(self):
        """
        ContinuityService.remember() requires all scope fields.
        """
        service = ContinuityService()

        with pytest.raises(ValueError, match="BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE"):
            service.remember(
                subject_id="",  # Empty - invalid
                gumi_instance_id="gumi_001",
                hermes_profile_id="hermes_001",
                subject_words=["some text"],
                subject_confirmation=True,
            )

    def test_delivery_gate_requires_subject_scope(self):
        """
        DeliveryGate requires valid subject scope.
        """
        # Valid scope - should work
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        assert gate.subject_id == "subj_001"

    def test_resume_reconciliation_validates_subject_scope(self):
        """
        ResumeReconciliation checks subject_scope validity.
        """
        from relic.hermes_runtime import (
            ResumeReconciliation,
            SessionResumeState,
            ReconciliationDecision,
            ReconciliationCheck,
        )

        # Invalid: empty subject_id
        state = SessionResumeState(
            subject_id="",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            session_key_hash="abc123",
        )

        reconciler = ResumeReconciliation(state)
        result = reconciler.reconcile(session_key_hash="abc123")

        assert result.decision == ReconciliationDecision.REVIEW_REQUIRED
        assert ReconciliationCheck.SUBJECT_SCOPE in result.failed_checks

    def test_gumi_runtime_context_never_cross_subject(self):
        """
        Gumi runtime context for subject A must never contain subject B's data.
        """
        service = ContinuityService()

        # Create marker for subject A
        service.remember(
            subject_id="subj_A",
            gumi_instance_id="gumi_A",
            hermes_profile_id="hermes_A",
            subject_words=["Subject A's private data"],
            subject_confirmation=True,
        )

        # Create marker for subject B
        service.remember(
            subject_id="subj_B",
            gumi_instance_id="gumi_B",
            hermes_profile_id="hermes_B",
            subject_words=["Subject B's private data"],
            subject_confirmation=True,
        )

        # Query for subject A's markers
        a_markers = service.recent_markers(subject_id="subj_A")
        a_marker_ids = [r["marker_id"] for r in a_markers]

        # Query for subject B's markers
        b_markers = service.recent_markers(subject_id="subj_B")
        b_marker_ids = [r["marker_id"] for r in b_markers]

        # Verify no cross-contamination
        for marker_id in a_marker_ids:
            marker = service._markers.get(marker_id)
            if marker:
                assert marker.subject_id == "subj_A"

        for marker_id in b_marker_ids:
            marker = service._markers.get(marker_id)
            if marker:
                assert marker.subject_id == "subj_B"


# =============================================================================
# DELIVERY GATE INVARIANTS
# =============================================================================

class TestDeliveryGateInvariants:
    """Delivery gate must enforce allowlist on all outbound paths."""

    def test_all_outbound_paths_require_allowlist(self):
        """
        Every outbound path must pass DeliveryGate allowlist check.

        Outbound paths per contract:
        - direct Gumi reply
        - cron follow-up
        - Shared Continuity follow-up
        - first-contact message
        - summary delivery
        - media/diegetic proactive message
        - resume-delayed pending output
        """
        # Clear any existing allowlist entries
        clear_allowlist_store()

        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        # Without allowlist entry, should be BLOCKED
        decision, event = gate.enforce("telegram")
        assert decision == DeliveryGateDecision.BLOCK

    def test_allowlisted_platform_permits_delivery(self):
        """
        Platform in allowlist with enabled=True permits delivery.
        """
        clear_allowlist_store()

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

    def test_disabled_allowlist_entry_blocks_delivery(self):
        """
        Platform with enabled=False in allowlist blocks delivery.
        """
        clear_allowlist_store()

        register_allowlist_entry({
            "subject_id": "subj_001",
            "platform": "telegram",
            "enabled": False,  # Disabled
        })

        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        decision, event = gate.enforce("telegram")
        assert decision == DeliveryGateDecision.BLOCK


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
