"""PR26E — PR33 Shared Continuity Data Contract tests."""

import pytest
import json
import jsonschema


class TestPR33DataContract:
    """Test suite for PR33 shared continuity data contract."""

    @pytest.fixture
    def continuity_marker_schema(self):
        """Load the continuity marker schema."""
        schema_path = "schemas/data-model/continuity_marker.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def valid_marker(self):
        """Valid continuity marker fixture."""
        return {
            "marker_id": "marker_001_e5f6g7h8",
            "subject_id": "subject_001",
            "gumi_instance_id": "gumi_instance_a1b2c3d4",
            "hermes_profile_id": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "marker_type": "session_continuity_state",
            "content_hash": "sha256:9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedcba",
            "confirmed": True,
            "created_at": "2024-01-15T16:00:00Z"
        }

    def test_continuity_marker_requires_subject_confirmation(self, valid_marker, continuity_marker_schema):
        """Continuity markers require subject confirmation for storage."""
        marker = valid_marker.copy()
        marker["confirmed"] = False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(marker, continuity_marker_schema)

    def test_continuity_marker_has_subject_id(self, valid_marker, continuity_marker_schema):
        """Continuity markers must have subject_id."""
        marker = valid_marker.copy()
        del marker["subject_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(marker, continuity_marker_schema)

    def test_recall_rules_defined(self, valid_marker, continuity_marker_schema):
        """Recall rules must be defined in schema."""
        assert "recall_rules" in continuity_marker_schema["properties"]
        rules = continuity_marker_schema["properties"]["recall_rules"]["properties"]
        assert "subject_can_recall" in rules
        assert "researcher_can_recall" in rules
        assert "gumi_can_recall" in rules

    def test_marker_not_clinical_interpretation(self, valid_marker, continuity_marker_schema):
        """Markers must not allow clinical interpretation."""
        marker = valid_marker.copy()
        marker["clinical_interpretation_allowed"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(marker, continuity_marker_schema)

    def test_marker_subject_scope_required(self, valid_marker, continuity_marker_schema):
        """Markers require complete subject scope."""
        required_fields = ["subject_id", "gumi_instance_id", "hermes_profile_id"]
        for field in required_fields:
            marker = valid_marker.copy()
            del marker[field]
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(marker, continuity_marker_schema)
