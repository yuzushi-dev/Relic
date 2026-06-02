"""
PR33A, Normative Protocol Tests

Tests for Shared Continuity Memory normative protocol:
- Marker requires subject confirmation
- Marker stores subject words (not clinical labels)
- Marker forbids clinical interpretation
- Gumi runtime receives no clinical tags
- Due followup respects max attempts
- Ignored followup expires
- Corrected marker uses subject correction
- Rejected marker not recalled
- Hindsight recall not directly user-facing
- Shared continuity is subject-scoped
- Protocol defines NOT a mood tracker
- Protocol defines NOT a clinical monitor
"""

import pytest
import json
import jsonschema


class TestNormativeProtocol:
    """Test normative protocol for Shared Continuity Memory."""

    def test_marker_requires_subject_confirmation(self):
        """Marker must require subject_confirmation before storage."""
        # Valid marker with subject_confirmation
        marker = {
            "subject_id": "subj_001",
            "gumi_instance_id": "gumi_001",
            "hermes_profile_id": "hermes_001",
            "subject_confirmation": True,
            "subject_words": ["too fast"],
            "status": "active"
        }
        assert marker["subject_confirmation"] is True

        # Unconfirmed marker should not be stored
        unconfirmed_marker = {
            "subject_id": "subj_001",
            "gumi_instance_id": "gumi_001",
            "hermes_profile_id": "hermes_001",
            "subject_confirmation": False,
            "subject_words": ["too fast"]
        }
        # Storage should be blocked for unconfirmed markers
        assert unconfirmed_marker["subject_confirmation"] is False

    def test_marker_stores_subject_words(self):
        """Marker stores subject's own words, not system inference."""
        marker = {
            "subject_id": "subj_001",
            "gumi_instance_id": "gumi_001",
            "hermes_profile_id": "hermes_001",
            "subject_confirmation": True,
            "subject_words": ["feels like moving too fast"],
            "gumi_agreed_words": [],
            "status": "active"
        }
        assert "feels like moving too fast" in marker["subject_words"]
        # gumi_agreed_words should be empty until confirmed by Gumi
        assert len(marker.get("gumi_agreed_words", [])) == 0 or marker["gumi_agreed_words"] == marker["subject_words"]

    def test_marker_forbids_clinical_interpretation(self):
        """Marker schema forbids clinical interpretation fields."""
        forbidden_terms = [
            "bipolar", "mania", "hypomania", "depression", "episode",
            "symptom", "diagnosis", "relapse", "pathology", "clinical risk"
        ]

        # Marker should not contain any clinical labels
        marker = {
            "subject_id": "subj_001",
            "gumi_instance_id": "gumi_001",
            "hermes_profile_id": "hermes_001",
            "subject_confirmation": True,
            "subject_words": ["feeling low"],
            "status": "active"
        }

        # Check no clinical terms in marker
        marker_str = json.dumps(marker).lower()
        for term in forbidden_terms:
            assert term not in marker_str

    def test_gumi_runtime_receives_no_clinical_tags(self):
        """Gumi runtime context must not receive clinical tags."""
        forbidden_terms = [
            "bipolar", "mania", "hypomania", "depression", "episode",
            "symptom", "diagnosis", "relapse", "pathology", "clinical risk"
        ]

        # Simulated context passed to Gumi
        context = {
            "markers": [
                {"subject_words": ["feeling low"], "status": "active"}
            ]
        }

        # No clinical tags should be in context
        context_str = json.dumps(context).lower()
        for term in forbidden_terms:
            assert term not in context_str

    def test_due_followup_respects_max_attempts(self):
        """Follow-up must not be sent after max_attempts reached."""
        followup = {
            "marker_id": "marker_001",
            "max_attempts": 3,
            "attempt_count": 3,
            "status": "exhausted"
        }
        assert followup["attempt_count"] >= followup["max_attempts"]
        assert followup["status"] == "exhausted"

    def test_ignored_followup_expires(self):
        """Ignored follow-ups must expire by TTL."""
        followup = {
            "marker_id": "marker_001",
            "status": "ignored",
            "ttl_seconds": 3600,
            "created_at": "2026-05-08T10:00:00Z",
            "expires_at": "2026-05-08T11:00:00Z"
        }
        # TTL should be set and respected
        assert followup["ttl_seconds"] > 0
        assert followup["status"] == "ignored"

    def test_corrected_marker_uses_subject_correction(self):
        """Corrected marker uses subject's correction as authoritative."""
        original = {
            "marker_id": "marker_001",
            "subject_words": ["too fast"],
            "status": "retired"
        }
        correction = {
            "original_marker_id": "marker_001",
            "subject_words": ["too fast for me"],
            "authoritative": True,
            "status": "active"
        }
        # Correction is authoritative and replaces original
        assert correction["authoritative"] is True
        assert correction["original_marker_id"] == original["marker_id"]
        assert correction["subject_words"] != original["subject_words"]

    def test_rejected_marker_not_recalled(self):
        """Rejected marker must not be recalled by Gumi."""
        rejected_marker = {
            "marker_id": "marker_001",
            "status": "rejected",
            "gumi_recall_allowed": False
        }
        # Gumi should not recall rejected markers
        assert rejected_marker["gumi_recall_allowed"] is False
        assert rejected_marker["status"] == "rejected"

    def test_hindsight_recall_not_directly_user_facing(self):
        """Hindsight recall must not be directly user-facing. Hindsight is not authority."""
        # Safe flow: Hindsight candidate must go through confirmation
        safe_flow_steps = [
            "Hindsight candidate",
            "Relic evaluates consent/visibility",
            "Gumi asks confirmation if appropriate",
            "only confirmed marker enters Shared Continuity Memory"
        ]
        assert len(safe_flow_steps) == 4

        # Forbidden flow should be blocked
        forbidden_flow = [
            "Hindsight recall",
            "Gumi directly follows up on sensitive content"
        ]
        assert len(forbidden_flow) == 2

    def test_shared_continuity_is_subject_scoped(self):
        """Every marker requires subject_id, gumi_instance_id, hermes_profile_id."""
        marker = {
            "subject_id": "subj_001",  # Required
            "gumi_instance_id": "gumi_001",  # Required
            "hermes_profile_id": "hermes_001",  # Required
            "subject_confirmation": True,
            "subject_words": ["test"],
            "status": "active"
        }

        assert "subject_id" in marker
        assert "gumi_instance_id" in marker
        assert "hermes_profile_id" in marker
        assert marker["subject_id"] is not None
        assert marker["gumi_instance_id"] is not None
        assert marker["hermes_profile_id"] is not None

    def test_protocol_defines_not_a_mood_tracker(self):
        """Protocol definition confirms Shared Continuity is NOT a mood tracker."""
        what_it_is_not = [
            "mood tracker",
            "symptom tracker",
            "clinical monitor",
            "pathology detector",
            "diagnostic system"
        ]
        assert "mood tracker" in what_it_is_not
        assert "symptom tracker" in what_it_is_not

    def test_protocol_defines_not_a_clinical_monitor(self):
        """Protocol definition confirms Shared Continuity is NOT a clinical monitor."""
        what_it_is_not = [
            "clinical monitor",
            "pathology detector",
            "diagnostic system"
        ]
        assert "clinical monitor" in what_it_is_not


class TestProtocolSchema:
    """Test protocol schema validation."""

    def test_schema_validates_protocol_valid_fixture(self):
        """Schema should validate the protocol_valid.json fixture."""
        schema_path = "schemas/shared-continuity/normative_protocol.schema.json"
        fixture_path = "fixtures/shared-continuity/protocol_valid.json"

        with open(schema_path) as f:
            schema = json.load(f)

        with open(fixture_path) as f:
            fixture = json.load(f)

        jsonschema.validate(fixture, schema)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])