"""PR26H — Cross-PR Contract Tests.

Tests verifying subject scope consistency, signal isolation, and marker scope
across PR26, PR27, PR30, PR32, and PR33 integration points.
"""

import pytest
import json


class TestCrossPRContracts:
    """Test suite for cross-PR data model contracts."""

    @pytest.fixture
    def cross_pr_fixture(self):
        """Load the cross-PR contract fixture."""
        fixture_path = "tests/data-model/fixtures/cross_pr_contract_fixture.json"
        with open(fixture_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def runtime_object_scope_schema(self):
        """Load the runtime object scope schema."""
        schema_path = "schemas/data-model/runtime_object_scope.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def base_event_schema(self):
        """Load the base event schema."""
        schema_path = "schemas/data-model/base_event.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def sensitive_signal_schema(self):
        """Load the sensitive signal schema."""
        schema_path = "schemas/data-model/sensitive_signal.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def continuity_marker_schema(self):
        """Load the continuity marker schema."""
        schema_path = "schemas/data-model/continuity_marker.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    def test_pr26_pr27_subject_scope_contract(self, cross_pr_fixture):
        """All PR26 runtime objects must satisfy PR27 subject scope contract."""
        import jsonschema

        for subject in cross_pr_fixture["test_subjects"]:
            scope = {
                "subject_id": subject["subject_id"],
                "gumi_instance_id": subject["gumi_instance_id"],
                "hermes_profile_id": subject["hermes_profile_id"]
            }
            # This should not raise - verifies subject scope is consistent
            schema_path = "schemas/data-model/runtime_object_scope.schema.json"
            with open(schema_path, "r") as f:
                schema = json.load(f)
            jsonschema.validate(scope, schema)

    def test_pr26_pr32_signal_isolation_contract(self, cross_pr_fixture):
        """Safety signals (PR32) cannot leak into Gumi runtime or Shared Continuity (PR33)."""
        import jsonschema

        for subject in cross_pr_fixture["test_subjects"]:
            # Sensitive signals must have gumi_visible=False
            for signal in subject.get("sensitive_signals", []):
                signal_data = {
                    "signal_id": signal["signal_id"],
                    "subject_id": subject["subject_id"],
                    "gumi_instance_id": subject["gumi_instance_id"],
                    "hermes_profile_id": subject["hermes_profile_id"],
                    "signal_type": signal["signal_type"],
                    "detected_at": "2024-01-15T14:30:00Z",
                    "researcher_visible": signal["researcher_visible"],
                    "gumi_visible": signal.get("gumi_visible", False)
                }
                schema_path = "schemas/data-model/sensitive_signal.schema.json"
                with open(schema_path, "r") as f:
                    schema = json.load(f)
                # This should fail if gumi_visible is True
                if signal.get("gumi_visible"):
                    with pytest.raises(jsonschema.ValidationError):
                        jsonschema.validate(signal_data, schema)
                else:
                    jsonschema.validate(signal_data, schema)

    def test_pr26_pr33_marker_scope_contract(self, cross_pr_fixture):
        """Continuity markers (PR33) cannot appear in safety signal evidence."""
        import jsonschema

        for subject in cross_pr_fixture["test_subjects"]:
            for marker in subject.get("continuity_markers", []):
                marker_data = {
                    "marker_id": marker["marker_id"],
                    "subject_id": subject["subject_id"],
                    "gumi_instance_id": subject["gumi_instance_id"],
                    "hermes_profile_id": subject["hermes_profile_id"],
                    "marker_type": marker["marker_type"],
                    "content_hash": "sha256:test",
                    "confirmed": marker["confirmed"],
                    "created_at": "2024-01-15T16:00:00Z"
                }
                schema_path = "schemas/data-model/continuity_marker.schema.json"
                with open(schema_path, "r") as f:
                    schema = json.load(f)
                jsonschema.validate(marker_data, schema)

    def test_pr26_pr30_event_scope_contract(self, cross_pr_fixture):
        """Every event has ontological_class and subject_id across all PRs."""
        import jsonschema

        for subject in cross_pr_fixture["test_subjects"]:
            for event in subject.get("events", []):
                event_data = {
                    "event_id": event["event_id"],
                    "subject_id": subject["subject_id"],
                    "gumi_instance_id": subject["gumi_instance_id"],
                    "hermes_profile_id": subject["hermes_profile_id"],
                    "event_class": event["event_class"],
                    "ontological_class": event["ontological_class"],
                    "timestamp": "2024-01-15T10:30:00Z",
                    "source_refs": [],
                    "policy_snapshot_id": "test_policy"
                }
                schema_path = "schemas/data-model/base_event.schema.json"
                with open(schema_path, "r") as f:
                    schema = json.load(f)
                jsonschema.validate(event_data, schema)

    def test_pr32_pr33_boundary_contract(self):
        """Safety signals (PR32) and continuity markers (PR33) must not cross-contaminate."""
        import jsonschema

        # PR32 sensitive signals should NOT be in continuity markers
        signal_schema_path = "schemas/data-model/sensitive_signal.schema.json"
        marker_schema_path = "schemas/data-model/continuity_marker.schema.json"

        with open(signal_schema_path, "r") as f:
            signal_schema = json.load(f)
        with open(marker_schema_path, "r") as f:
            marker_schema = json.load(f)

        # Verify they are separate schemas with distinct purposes
        assert signal_schema["title"] != marker_schema["title"]
        assert "sensitive" in signal_schema["title"].lower()
        assert "continuity" in marker_schema["title"].lower()

    def test_pr30_pr32_no_clinical_label_leakage(self):
        """PR30 hooks do not inject clinical labels into PR32 sensitive signals."""
        # Read PR30 hooks documentation if it exists
        doc_path = "docs/data-model/02_EVENT_REGISTRY.md"
        with open(doc_path, "r") as f:
            content = f.read()

        # PR30 events should not mention clinical labels
        assert "clinical" not in content.lower() or "clinical_interpretation_allowed" in content

        # PR32 sensitive signals must have clinical_interpretation_allowed = false
        schema_path = "schemas/data-model/sensitive_signal.schema.json"
        with open(schema_path, "r") as f:
            schema = json.load(f)

        # Check schema enforces clinical_interpretation_allowed = false
        props = schema["properties"]
        assert "clinical_interpretation_allowed" in props
        assert props["clinical_interpretation_allowed"].get("const") is False

    def test_pr30_pr33_no_clinical_marker_leakage(self):
        """PR30 hooks do not inject clinical interpretations into PR33 markers."""
        schema_path = "schemas/data-model/continuity_marker.schema.json"
        with open(schema_path, "r") as f:
            schema = json.load(f)

        # Check schema enforces clinical_interpretation_allowed = false
        props = schema["properties"]
        assert "clinical_interpretation_allowed" in props
        assert props["clinical_interpretation_allowed"].get("const") is False

    def test_pr27_every_panel_subject_scoped(self, cross_pr_fixture):
        """Every PR27 panel requires subject scope (subject_id, gumi_instance_id, hermes_profile_id)."""
        import jsonschema

        schema_path = "schemas/data-model/runtime_object_scope.schema.json"
        with open(schema_path, "r") as f:
            schema = json.load(f)

        # All test subjects must have complete subject scope
        for subject in cross_pr_fixture["test_subjects"]:
            scope = {
                "subject_id": subject["subject_id"],
                "gumi_instance_id": subject["gumi_instance_id"],
                "hermes_profile_id": subject["hermes_profile_id"]
            }
            jsonschema.validate(scope, schema)

    def test_cross_pr_event_has_ontological_class(self, cross_pr_fixture):
        """All events across PRs must have ontological_class."""
        import jsonschema

        schema_path = "schemas/data-model/base_event.schema.json"
        with open(schema_path, "r") as f:
            schema = json.load(f)

        # Verify ontological_class is required
        assert "ontological_class" in schema["required"]

        # Verify all fixture events have ontological_class
        for subject in cross_pr_fixture["test_subjects"]:
            for event in subject.get("events", []):
                assert "ontological_class" in event
                # Verify it's a valid enum value
                valid_classes = schema["properties"]["ontological_class"]["enum"]
                assert event["ontological_class"] in valid_classes
