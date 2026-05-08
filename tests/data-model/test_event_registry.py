"""PR26B — Event Registry tests."""

import pytest
import json
import jsonschema


class TestEventRegistry:
    """Test suite for event registry contract."""

    @pytest.fixture
    def base_event_schema(self):
        """Load the base event schema."""
        schema_path = "schemas/data-model/base_event.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def valid_event(self):
        """Valid base event fixture."""
        return {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "subject_id": "subject_001",
            "gumi_instance_id": "gumi_instance_a1b2c3d4",
            "hermes_profile_id": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "event_class": "governance_decision",
            "ontological_class": "governance_decision",
            "timestamp": "2024-01-15T10:30:00Z",
            "source_refs": ["cron/schedule/daily_marker_recall"],
            "policy_snapshot_id": "policy_v2.3_sha256:abc123def456"
        }

    def test_event_has_subject_id(self, valid_event, base_event_schema):
        """Every event must have a subject_id."""
        event = valid_event.copy()
        del event["subject_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(event, base_event_schema)

    def test_event_has_ontological_class(self, valid_event, base_event_schema):
        """Every event must have an ontological_class."""
        event = valid_event.copy()
        del event["ontological_class"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(event, base_event_schema)

    def test_event_metadata_redaction_defined(self, valid_event, base_event_schema):
        """Event metadata redaction rules must be defined in schema."""
        assert "metadata" in base_event_schema["properties"]
        metadata_props = base_event_schema["properties"]["metadata"]["properties"]
        assert "raw_text_redacted" in metadata_props
        assert "provider_logs_access" in metadata_props
        assert "session_key_stored_as_hash" in metadata_props

    def test_pr30_events_registered(self):
        """PR30 events must be documented in the event registry."""
        doc_path = "docs/data-model/02_EVENT_REGISTRY.md"
        with open(doc_path, "r") as f:
            content = f.read()
        assert "hermes_transform_llm_output" in content
        assert "hermes_no_agent" in content

    def test_pr32_events_registered(self):
        """PR32 events must be documented in the event registry."""
        doc_path = "docs/data-model/02_EVENT_REGISTRY.md"
        with open(doc_path, "r") as f:
            content = f.read()
        assert "sensitive_pattern_detected" in content
        assert "behavior_policy_patch_applied" in content

    def test_pr33_events_registered(self):
        """PR33 events must be documented in the event registry."""
        doc_path = "docs/data-model/02_EVENT_REGISTRY.md"
        with open(doc_path, "r") as f:
            content = f.read()
        assert "continuity_marker_created" in content
        assert "continuity_marker_corrected" in content

    def test_event_source_refs_defined(self, valid_event, base_event_schema):
        """Every event must have source_refs defined."""
        assert "source_refs" in base_event_schema["required"]
        event = valid_event.copy()
        del event["source_refs"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(event, base_event_schema)
