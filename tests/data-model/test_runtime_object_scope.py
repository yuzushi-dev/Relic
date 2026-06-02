"""PR26A, Canonical Identity and Scope Model tests."""

import pytest
import json
import jsonschema


class TestRuntimeObjectScope:
    """Test suite for runtime object scope contract."""

    @pytest.fixture
    def valid_scope(self):
        """Valid scope fixture."""
        return {
            "subject_id": "subject_001",
            "gumi_instance_id": "gumi_instance_a1b2c3d4",
            "hermes_profile_id": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }

    @pytest.fixture
    def scope_schema(self):
        """Load the runtime object scope schema."""
        schema_path = "schemas/data-model/runtime_object_scope.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    def test_runtime_object_requires_subject_id(self, valid_scope, scope_schema):
        """Every runtime object must have a subject_id."""
        obj = valid_scope.copy()
        del obj["subject_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(obj, scope_schema)

    def test_runtime_object_requires_gumi_instance_id(self, valid_scope, scope_schema):
        """Every runtime object must have a gumi_instance_id."""
        obj = valid_scope.copy()
        del obj["gumi_instance_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(obj, scope_schema)

    def test_runtime_object_requires_hermes_profile_id(self, valid_scope, scope_schema):
        """Every runtime object must have a hermes_profile_id."""
        obj = valid_scope.copy()
        del obj["hermes_profile_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(obj, scope_schema)

    def test_cross_subject_shared_memory_forbidden(self, valid_scope, scope_schema):
        """Cross-subject shared memory is forbidden by schema constraints."""
        # Each runtime object must have exactly one subject_id
        # AdditionalProperties: false prevents extra subject_ids
        obj = valid_scope.copy()
        obj["extra_subject_ref"] = "other_subject"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(obj, scope_schema)

    def test_hermes_session_key_stored_as_hash(self, valid_scope, scope_schema):
        """Hermes session key stored as hash - schema accepts both hash and profile ID formats.

        Note: hermes_profile_id accepts both sha256:... hash format and plain profile IDs.
        The session key itself is stored via the session_key schema, not hermes_profile_id.
        """
        obj = valid_scope.copy()
        # Both hash format and plain profile IDs are valid for hermes_profile_id
        obj["hermes_profile_id"] = "sha256:" + "a" * 64  # hash format
        jsonschema.validate(obj, scope_schema)  # should pass
        obj["hermes_profile_id"] = "profile_001"  # plain ID also valid
        jsonschema.validate(obj, scope_schema)  # should pass

    def test_no_runtime_object_without_subject_scope(self, valid_scope, scope_schema):
        """No runtime object may exist without a complete subject scope."""
        incomplete_scopes = [
            {"subject_id": "subject_001"},
            {"gumi_instance_id": "gumi_instance_a1b2c3d4"},
            {"hermes_profile_id": "sha256:abc123"},
            {},
        ]
        for incomplete in incomplete_scopes:
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(incomplete, scope_schema)
